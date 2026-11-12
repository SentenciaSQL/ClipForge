"""Transcribe a clip audio track and align subtitle overrides to it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.ai.transcription.whisper_service import whisper_service
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import AudioTrack, Clip
from app.media.ffmpeg import extract_audio_wav
from app.schemas.clip_config import SubtitleSegmentOverride
from app.services.clip_config import get_clip_configuration, save_clip_configuration

logger = get_logger(__name__)

SPEECH_TRACK_TYPES = {"replacement", "voiceover"}


def _clip_relative_segments(
    result_segments: list[Any],
    *,
    offset_seconds: float,
    clip_duration: float,
) -> list[SubtitleSegmentOverride]:
    """Map Whisper file-relative segments into clip-relative subtitle overrides."""
    out: list[SubtitleSegmentOverride] = []
    for seg in result_segments:
        text = str(getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        start = float(getattr(seg, "start", 0.0) or 0.0) + float(offset_seconds or 0.0)
        end = float(getattr(seg, "end", start + 0.5) or (start + 0.5)) + float(offset_seconds or 0.0)
        # Keep only the portion that overlaps the clip timeline.
        start = max(0.0, start)
        end = min(float(clip_duration), end)
        if end - start < 0.05:
            continue
        out.append(SubtitleSegmentOverride(text=text, start=round(start, 3), end=round(end, 3)))
    return out


def transcribe_track_for_subtitles(
    db: Session,
    clip_id: str,
    track_id: str,
    *,
    language: str | None = None,
    whisper_model: str | None = None,
) -> dict[str, Any]:
    """
    Run Whisper on a replacement/voiceover track and write clip subtitle segments.

    Returns a summary dict suitable for job.result_json.
    """
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ValueError("Clip not found")
    track = db.get(AudioTrack, track_id)
    if not track or track.clip_id != clip.id:
        raise ValueError("Audio track not found for this clip")
    if track.track_type not in SPEECH_TRACK_TYPES:
        raise ValueError("Only replacement or voiceover tracks can drive subtitle transcription")
    if not track.source_path:
        raise ValueError("Track has no audio file")

    source = Path(track.source_path)
    if not source.exists():
        raise FileNotFoundError(f"Track audio missing: {source}")

    settings = get_settings()
    wav_path = settings.temporary_dir / "clip-audio-tx" / clip.id / f"{track.id}_16k.wav"
    extract_audio_wav(source, wav_path, sample_rate=16000)

    result = whisper_service.transcribe(
        wav_path,
        # Use path-safe ids only — Windows rejects ':' in directory names.
        video_id=f"clip-audio_{clip.id}_{track.id}",
        model_name=whisper_model,
        language=language or None,
        use_cache=True,
    )

    segments = _clip_relative_segments(
        result.segments,
        offset_seconds=float(track.offset_seconds or 0.0),
        clip_duration=float(clip.duration_seconds or 0.0) or float(result.duration_seconds or 0.0) or 1.0,
    )
    if not segments:
        raise ValueError("No speech detected in the uploaded audio for subtitles")

    cfg = get_clip_configuration(db, clip)
    cfg.subtitles.enabled = True
    cfg.subtitles.segments = segments
    save_clip_configuration(db, clip, cfg)

    # Keep the clip transcript text aligned with the spoken replacement audio.
    clip.transcript = (result.full_text or "").strip() or clip.transcript
    meta = dict(track.metadata_json or {})
    meta["subtitle_transcription"] = {
        "language": result.language,
        "model_name": result.model_name,
        "device": result.device,
        "segment_count": len(segments),
        "word_count": len(result.words),
        "full_text_preview": (result.full_text or "")[:500],
    }
    track.metadata_json = meta
    db.commit()
    db.refresh(clip)

    logger.info(
        "Aligned %s subtitle segments for clip %s from track %s (%s)",
        len(segments),
        clip.id,
        track.id,
        track.track_type,
    )
    return {
        "clip_id": clip.id,
        "track_id": track.id,
        "track_type": track.track_type,
        "segment_count": len(segments),
        "language": result.language,
        "model_name": result.model_name,
        "device": result.device,
        "full_text_preview": (result.full_text or "")[:500],
    }
