"""Optional speaker diarization: local energy clustering, or pyannote when available."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

DiarizationEngine = Literal["auto", "local", "pyannote"]


@dataclass
class SpeakerSegment:
    speaker_label: str
    start: float
    end: float
    confidence: float | None = None


@dataclass
class DiarizationResult:
    engine: str
    speakers: list[str]
    segments: list[SpeakerSegment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "speakers": self.speakers,
            "segments": [asdict(seg) for seg in self.segments],
            "notes": self.notes,
        }


def _hf_token() -> str | None:
    settings = get_settings()
    token = getattr(settings, "hf_token", None) or None
    if token:
        return str(token)
    import os

    return os.environ.get("AVC_HF_TOKEN") or os.environ.get("HF_TOKEN") or None


def pyannote_available() -> bool:
    try:
        import pyannote.audio  # noqa: F401

        return True
    except Exception:
        return False


def _load_mono(path: Path, start: float = 0.0, duration: float | None = None) -> tuple[np.ndarray, int]:
    import soundfile as sf

    with sf.SoundFile(str(path)) as handle:
        sr = int(handle.samplerate)
        start_frame = max(0, int(start * sr))
        handle.seek(start_frame)
        frames = duration if duration is None else int(duration * sr)
        audio = handle.read(frames if duration is not None else -1, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = np.mean(audio, axis=1)
    return np.asarray(audio, dtype=np.float32), sr


def _frame_features(audio: np.ndarray, sr: int, frame_ms: float = 400.0, hop_ms: float = 200.0) -> tuple[np.ndarray, np.ndarray]:
    frame = max(int(sr * frame_ms / 1000.0), 1)
    hop = max(int(sr * hop_ms / 1000.0), 1)
    feats: list[list[float]] = []
    times: list[float] = []
    if len(audio) < frame:
        return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)

    for start in range(0, len(audio) - frame + 1, hop):
        chunk = audio[start : start + frame]
        rms = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
        if rms < 0.01:
            continue
        # Zero-crossing rate
        zcr = float(np.mean(np.abs(np.diff(np.signbit(chunk).astype(np.int8)))))
        # Spectral centroid via rFFT magnitude
        spectrum = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
        freqs = np.fft.rfftfreq(len(chunk), d=1.0 / sr)
        denom = float(np.sum(spectrum) + 1e-12)
        centroid = float(np.sum(freqs * spectrum) / denom)
        # Spectral rolloff approx
        cumsum = np.cumsum(spectrum)
        rolloff_idx = int(np.searchsorted(cumsum, 0.85 * cumsum[-1]))
        rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])
        feats.append([rms, zcr, centroid / max(sr / 2, 1), rolloff / max(sr / 2, 1)])
        times.append((start + frame / 2) / sr)
    if not feats:
        return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.float32)
    return np.asarray(feats, dtype=np.float32), np.asarray(times, dtype=np.float32)


def _kmeans(features: np.ndarray, k: int, iterations: int = 25) -> np.ndarray:
    if len(features) == 0:
        return np.zeros((0,), dtype=np.int32)
    k = max(1, min(k, len(features)))
    # Init with spread indices
    indices = np.linspace(0, len(features) - 1, k, dtype=int)
    centers = features[indices].copy()
    labels = np.zeros(len(features), dtype=np.int32)
    for _ in range(iterations):
        distances = np.linalg.norm(features[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(distances, axis=1).astype(np.int32)
        for cluster in range(k):
            members = features[labels == cluster]
            if len(members):
                centers[cluster] = np.mean(members, axis=0)
    return labels


def _segments_from_labels(times: np.ndarray, labels: np.ndarray, frame_seconds: float = 0.2) -> list[SpeakerSegment]:
    if len(times) == 0:
        return []
    segments: list[SpeakerSegment] = []
    current = int(labels[0])
    start = float(max(0.0, times[0] - frame_seconds / 2))
    prev_t = float(times[0])
    for t, label in zip(times[1:], labels[1:], strict=False):
        label_i = int(label)
        if label_i != current:
            end = float((prev_t + float(t)) / 2)
            if end > start:
                segments.append(
                    SpeakerSegment(
                        speaker_label=f"SPEAKER_{current:02d}",
                        start=start,
                        end=end,
                    )
                )
            current = label_i
            start = end
        prev_t = float(t)
    segments.append(
        SpeakerSegment(
            speaker_label=f"SPEAKER_{current:02d}",
            start=start,
            end=float(prev_t + frame_seconds / 2),
        )
    )
    return segments


def diarize_local(
    audio_path: Path,
    *,
    max_speakers: int = 2,
    min_speakers: int = 1,
) -> DiarizationResult:
    audio, sr = _load_mono(audio_path)
    features, times = _frame_features(audio, sr)
    notes = ["local energy/spectral clustering (no cloud, no HF token)"]
    if len(features) < 4:
        notes.append("too little voiced audio; defaulting to single speaker")
        duration = len(audio) / float(sr) if sr else 0.0
        return DiarizationResult(
            engine="local",
            speakers=["SPEAKER_00"],
            segments=[SpeakerSegment("SPEAKER_00", 0.0, duration)],
            notes=notes,
        )

    # Normalize features
    mean = np.mean(features, axis=0)
    std = np.std(features, axis=0) + 1e-6
    normed = (features - mean) / std

    # Choose k by simple inertia elbow between min/max
    best_k = min_speakers
    best_score = float("inf")
    for k in range(min_speakers, max_speakers + 1):
        labels = _kmeans(normed, k)
        centers = np.vstack(
            [
                np.mean(normed[labels == cluster], axis=0)
                if np.any(labels == cluster)
                else np.zeros(normed.shape[1])
                for cluster in range(k)
            ]
        )
        inertia = float(np.sum((normed - centers[labels]) ** 2))
        # Penalize more clusters lightly
        score = inertia + (0.15 * k * len(normed))
        if score < best_score:
            best_score = score
            best_k = k

    labels = _kmeans(normed, best_k)
    segments = _segments_from_labels(times, labels)
    # Merge micro-segments < 0.4s into neighbors
    merged: list[SpeakerSegment] = []
    for seg in segments:
        if merged and (seg.end - seg.start) < 0.4:
            merged[-1].end = seg.end
            continue
        if merged and merged[-1].speaker_label == seg.speaker_label:
            merged[-1].end = seg.end
        else:
            merged.append(seg)
    speakers = sorted({seg.speaker_label for seg in merged})
    return DiarizationResult(engine="local", speakers=speakers, segments=merged, notes=notes)


def diarize_pyannote(audio_path: Path, *, max_speakers: int | None = 2) -> DiarizationResult:
    token = _hf_token()
    if not token:
        raise RuntimeError(
            "Pyannote requires a Hugging Face token. Set AVC_HF_TOKEN (free account) "
            "and accept model terms, or use engine='local'."
        )
    try:
        from pyannote.audio import Pipeline  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "pyannote.audio is not installed. pip install pyannote.audio (optional)."
        ) from exc

    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    params: dict[str, Any] = {}
    if max_speakers:
        params["max_speakers"] = max_speakers
    annotation = pipeline(str(audio_path), **params) if params else pipeline(str(audio_path))

    segments: list[SpeakerSegment] = []
    speakers: set[str] = set()
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        label = str(speaker)
        speakers.add(label)
        segments.append(SpeakerSegment(speaker_label=label, start=float(turn.start), end=float(turn.end)))
    return DiarizationResult(
        engine="pyannote",
        speakers=sorted(speakers),
        segments=segments,
        notes=["pyannote/speaker-diarization-3.1 (local inference)"],
    )


def diarize_audio(
    audio_path: Path,
    *,
    engine: DiarizationEngine = "auto",
    max_speakers: int = 2,
) -> DiarizationResult:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio not found: {path}")

    chosen = engine
    if engine == "auto":
        if pyannote_available() and _hf_token():
            chosen = "pyannote"
        else:
            chosen = "local"

    if chosen == "pyannote":
        try:
            return diarize_pyannote(path, max_speakers=max_speakers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pyannote diarization failed (%s); falling back to local", exc)
            result = diarize_local(path, max_speakers=max_speakers)
            result.notes.append(f"pyannote fallback: {exc}")
            return result
    return diarize_local(path, max_speakers=max_speakers)


def assign_speakers_to_words(
    words: list[dict[str, Any]],
    segments: list[SpeakerSegment],
) -> list[dict[str, Any]]:
    """Attach speaker_label to each word by midpoint overlap."""
    if not segments:
        return words
    enriched: list[dict[str, Any]] = []
    for word in words:
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        mid = (start + end) / 2.0
        label = None
        for seg in segments:
            if seg.start <= mid <= seg.end:
                label = seg.speaker_label
                break
        if label is None:
            # nearest segment
            nearest = min(segments, key=lambda s: min(abs(mid - s.start), abs(mid - s.end)))
            label = nearest.speaker_label
        item = dict(word)
        item["speaker_label"] = label
        enriched.append(item)
    return enriched
