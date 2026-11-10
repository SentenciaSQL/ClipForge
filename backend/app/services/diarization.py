"""Persist and query speaker diarization results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.diarization.service import (
    DiarizationEngine,
    assign_speakers_to_words,
    diarize_audio,
    pyannote_available,
)
from app.core.config import get_settings
from app.core.gpu_manager import gpu_manager
from app.core.logging import get_logger
from app.database.models import Speaker, SourceVideo, Transcription, TranscriptionWord
from app.services.transcriptions import extract_audio_for_video, get_latest_transcription

logger = get_logger(__name__)


def list_speakers(db: Session, video_id: str) -> list[Speaker]:
    return list(
        db.scalars(select(Speaker).where(Speaker.video_id == video_id).order_by(Speaker.label.asc())).all()
    )


def rename_speaker(db: Session, speaker_id: str, display_name: str) -> Speaker:
    speaker = db.get(Speaker, speaker_id)
    if not speaker:
        raise ValueError("Speaker not found")
    speaker.display_name = display_name
    db.commit()
    db.refresh(speaker)
    return speaker


def run_diarization_for_video(
    db: Session,
    video_id: str,
    *,
    engine: DiarizationEngine | None = None,
    max_speakers: int | None = None,
) -> dict[str, Any]:
    video = db.get(SourceVideo, video_id)
    if not video:
        raise ValueError("Video not found")

    settings = get_settings()
    audio_path = extract_audio_for_video(video)
    chosen_engine = engine or settings.diarization_engine
    speakers_cap = max_speakers or settings.diarization_max_speakers

    gpu_manager.prepare_for_llm()
    acquired = gpu_manager.acquire("unknown", timeout=3600)
    if not acquired:
        raise RuntimeError("Timed out waiting for GPU lock for diarization")
    try:
        result = diarize_audio(
            Path(audio_path),
            engine=chosen_engine,  # type: ignore[arg-type]
            max_speakers=speakers_cap,
        )
    finally:
        gpu_manager.release()

    # Replace previous speakers for this video
    db.execute(delete(Speaker).where(Speaker.video_id == video_id))
    db.flush()

    speaker_rows: dict[str, Speaker] = {}
    for index, label in enumerate(result.speakers):
        row = Speaker(
            video_id=video_id,
            label=label,
            display_name=f"Speaker {index + 1}",
            metadata_json={"engine": result.engine},
        )
        db.add(row)
        db.flush()
        speaker_rows[label] = row

    transcription = get_latest_transcription(db, video_id)
    word_updates = 0
    if transcription:
        # Enrich segments_json words
        segments = list(transcription.segments_json or [])
        flat_words: list[dict[str, Any]] = []
        for seg in segments:
            for word in seg.get("words") or []:
                flat_words.append(word)
        enriched = assign_speakers_to_words(flat_words, result.segments)
        # rebuild with speaker labels
        cursor = 0
        new_segments = []
        for seg in segments:
            words = list(seg.get("words") or [])
            new_words = []
            for word in words:
                item = dict(word)
                if cursor < len(enriched):
                    item["speaker_label"] = enriched[cursor].get("speaker_label")
                    cursor += 1
                new_words.append(item)
            new_seg = dict(seg)
            new_seg["words"] = new_words
            # majority speaker for segment
            labels = [w.get("speaker_label") for w in new_words if w.get("speaker_label")]
            if labels:
                new_seg["speaker_label"] = max(set(labels), key=labels.count)
            new_segments.append(new_seg)
        transcription.segments_json = new_segments

        # Update TranscriptionWord rows
        word_rows = db.scalars(
            select(TranscriptionWord)
            .where(TranscriptionWord.transcription_id == transcription.id)
            .order_by(TranscriptionWord.index.asc())
        ).all()
        for row, enriched_word in zip(word_rows, enriched, strict=False):
            label = enriched_word.get("speaker_label")
            speaker = speaker_rows.get(label) if label else None
            row.speaker_id = speaker.id if speaker else None
            word_updates += 1

    db.commit()
    logger.info(
        "Diarized video=%s engine=%s speakers=%s words=%s",
        video_id,
        result.engine,
        len(result.speakers),
        word_updates,
    )
    return {
        "video_id": video_id,
        "engine": result.engine,
        "speakers": [
            {
                "id": speaker_rows[label].id,
                "label": label,
                "display_name": speaker_rows[label].display_name,
            }
            for label in result.speakers
            if label in speaker_rows
        ],
        "segments": result.to_dict()["segments"],
        "notes": result.notes,
        "pyannote_available": pyannote_available(),
        "word_updates": word_updates,
        "transcription_id": transcription.id if transcription else None,
    }
