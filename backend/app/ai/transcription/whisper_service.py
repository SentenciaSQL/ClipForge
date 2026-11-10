"""Local Faster-Whisper transcription with GPU/CPU adaptation."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.config import get_settings
from app.core.hardware import detect_hardware
from app.core.logging import get_logger

logger = get_logger(__name__)

WhisperModelName = Literal["large-v3", "distil-large-v3", "medium", "small", "base", "tiny"]


@dataclass
class WordStamp:
    word: str
    start: float
    end: float
    confidence: float | None = None


@dataclass
class SegmentStamp:
    id: int
    start: float
    end: float
    text: str
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    words: list[WordStamp] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    language: str | None
    language_probability: float | None
    duration_seconds: float | None
    model_name: str
    device: str
    compute_type: str
    full_text: str
    segments: list[SegmentStamp]
    words: list[WordStamp]
    audio_path: str
    cache_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "duration_seconds": self.duration_seconds,
            "model_name": self.model_name,
            "device": self.device,
            "compute_type": self.compute_type,
            "full_text": self.full_text,
            "segments": [
                {
                    **{k: v for k, v in asdict(seg).items() if k != "words"},
                    "words": [asdict(w) for w in seg.words],
                }
                for seg in self.segments
            ],
            "words": [asdict(w) for w in self.words],
            "audio_path": self.audio_path,
            "cache_key": self.cache_key,
        }


class WhisperService:
    """Lazy-loaded Faster-Whisper singleton with exclusive GPU access."""

    def __init__(self) -> None:
        self._model = None
        self._loaded_key: tuple[str, str, str] | None = None
        self._lock = threading.Lock()

    def resolve_device(self, requested: str | None = None) -> str:
        settings = get_settings()
        hardware = detect_hardware()
        choice = (requested or settings.whisper_device or "auto").lower()
        if choice == "auto":
            return "cuda" if hardware.cuda_available and settings.prefer_gpu else "cpu"
        if choice == "cuda" and not hardware.cuda_available:
            logger.warning("CUDA requested but unavailable; falling back to CPU")
            return "cpu"
        return choice

    def resolve_compute_type(self, device: str, requested: str | None = None) -> str:
        settings = get_settings()
        choice = (requested or settings.whisper_compute_type or "auto").lower()
        if choice != "auto":
            return choice
        return "float16" if device == "cuda" else "int8"

    def recommend_model(self, requested: str | None = None) -> str:
        settings = get_settings()
        model = requested or settings.whisper_model or "large-v3"
        hardware = detect_hardware()
        if self.resolve_device() == "cpu" and model in {"large-v3", "distil-large-v3"}:
            # Keep the configured model, but log that CPU will be slow.
            logger.info(
                "Using Whisper model '%s' on CPU (slow). Consider 'small' or 'medium' for CPU-only machines.",
                model,
            )
        elif hardware.cuda_available and hardware.gpu_vram_gb is not None and hardware.gpu_vram_gb < 6:
            if model == "large-v3":
                logger.info("Low VRAM detected (%.1f GB); large-v3 may require sequential GPU locking.", hardware.gpu_vram_gb)
        return model

    def _load_model(self, model_name: str, device: str, compute_type: str):
        key = (model_name, device, compute_type)
        if self._model is not None and self._loaded_key == key:
            return self._model

        # Unload previous model before loading another to conserve VRAM/RAM.
        self._model = None
        self._loaded_key = None

        from faster_whisper import WhisperModel

        logger.info("Loading Faster-Whisper model=%s device=%s compute=%s", model_name, device, compute_type)
        self._model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self._loaded_key = key
        return self._model

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._loaded_key = None

    def _load_audio_array(self, audio_path: Path):
        """Return float32 mono PCM for Faster-Whisper without going through PyAV."""
        import numpy as np
        import soundfile as sf

        audio, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = np.mean(audio, axis=1)
        if sample_rate != 16000:
            # Lightweight linear resample for unexpected rates.
            duration = len(audio) / float(sample_rate)
            target_length = max(int(duration * 16000), 1)
            x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
            audio = np.interp(x_new, x_old, audio).astype(np.float32)
        return audio

    def cache_key(self, audio_path: Path, model_name: str, language: str | None) -> str:
        stat = audio_path.stat()
        digest = hashlib.sha256()
        digest.update(str(audio_path.resolve()).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(int(stat.st_mtime)).encode("utf-8"))
        digest.update(model_name.encode("utf-8"))
        digest.update((language or "auto").encode("utf-8"))
        return digest.hexdigest()

    def cache_path(self, video_id: str, key: str) -> Path:
        settings = get_settings()
        directory = settings.temporary_dir / video_id / "transcription_cache"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.json"

    def load_cache(self, path: Path) -> TranscriptionResult | None:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            segments = [
                SegmentStamp(
                    id=int(seg.get("id", idx)),
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    text=str(seg.get("text", "")),
                    avg_logprob=seg.get("avg_logprob"),
                    no_speech_prob=seg.get("no_speech_prob"),
                    words=[
                        WordStamp(
                            word=str(w["word"]),
                            start=float(w["start"]),
                            end=float(w["end"]),
                            confidence=w.get("confidence"),
                        )
                        for w in seg.get("words", [])
                    ],
                )
                for idx, seg in enumerate(raw.get("segments", []))
            ]
            words = [
                WordStamp(
                    word=str(w["word"]),
                    start=float(w["start"]),
                    end=float(w["end"]),
                    confidence=w.get("confidence"),
                )
                for w in raw.get("words", [])
            ]
            return TranscriptionResult(
                language=raw.get("language"),
                language_probability=raw.get("language_probability"),
                duration_seconds=raw.get("duration_seconds"),
                model_name=raw.get("model_name", ""),
                device=raw.get("device", ""),
                compute_type=raw.get("compute_type", ""),
                full_text=raw.get("full_text", ""),
                segments=segments,
                words=words,
                audio_path=raw.get("audio_path", ""),
                cache_key=raw.get("cache_key", ""),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Ignoring invalid transcription cache %s: %s", path, exc)
            return None

    def save_cache(self, path: Path, result: TranscriptionResult) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False), encoding="utf-8")

    def transcribe(
        self,
        audio_path: Path,
        *,
        video_id: str,
        model_name: str | None = None,
        language: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        use_cache: bool = True,
    ) -> TranscriptionResult:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        resolved_model = self.recommend_model(model_name)
        resolved_device = self.resolve_device(device)
        resolved_compute = self.resolve_compute_type(resolved_device, compute_type)
        key = self.cache_key(audio_path, resolved_model, language)
        cache_file = self.cache_path(video_id, key)

        if use_cache:
            cached = self.load_cache(cache_file)
            if cached is not None:
                logger.info("Transcription cache hit for video=%s model=%s", video_id, resolved_model)
                cached.audio_path = str(audio_path)
                cached.cache_key = key
                return cached

        with self._lock:
            model = self._load_model(resolved_model, resolved_device, resolved_compute)
            # Load WAV ourselves to avoid PyAV API mismatches with faster-whisper.
            audio_input: Any = self._load_audio_array(audio_path)
            segments_iter, info = model.transcribe(
                audio_input,
                language=language,
                beam_size=5,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
            )

            segments: list[SegmentStamp] = []
            words: list[WordStamp] = []
            texts: list[str] = []
            for index, segment in enumerate(segments_iter):
                seg_words: list[WordStamp] = []
                for word in segment.words or []:
                    stamp = WordStamp(
                        word=word.word,
                        start=float(word.start),
                        end=float(word.end),
                        confidence=float(word.probability) if word.probability is not None else None,
                    )
                    seg_words.append(stamp)
                    words.append(stamp)
                text = (segment.text or "").strip()
                if text:
                    texts.append(text)
                segments.append(
                    SegmentStamp(
                        id=index,
                        start=float(segment.start),
                        end=float(segment.end),
                        text=text,
                        avg_logprob=float(segment.avg_logprob) if segment.avg_logprob is not None else None,
                        no_speech_prob=float(segment.no_speech_prob)
                        if segment.no_speech_prob is not None
                        else None,
                        words=seg_words,
                    )
                )

            result = TranscriptionResult(
                language=getattr(info, "language", None),
                language_probability=float(info.language_probability)
                if getattr(info, "language_probability", None) is not None
                else None,
                duration_seconds=float(info.duration) if getattr(info, "duration", None) is not None else None,
                model_name=resolved_model,
                device=resolved_device,
                compute_type=resolved_compute,
                full_text=" ".join(texts).strip(),
                segments=segments,
                words=words,
                audio_path=str(audio_path),
                cache_key=key,
            )

        if use_cache:
            self.save_cache(cache_file, result)
        logger.info(
            "Transcribed video=%s lang=%s segments=%s words=%s model=%s",
            video_id,
            result.language,
            len(result.segments),
            len(result.words),
            result.model_name,
        )
        return result


whisper_service = WhisperService()
