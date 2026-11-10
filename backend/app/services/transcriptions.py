"""Persist and query transcriptions."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.ai.transcription.whisper_service import TranscriptionResult
from app.database.models import SourceVideo, Transcription, TranscriptionWord
from app.media.ffmpeg import extract_audio_wav
from app.schemas.transcriptions import SegmentOut, TranscriptionOut, WordOut
from app.storage.paths import video_temp_dir


def extract_audio_for_video(video: SourceVideo) -> Path:
    temp_dir = video_temp_dir(video.id)
    audio_path = temp_dir / "audio_16k_mono.wav"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        source = Path(video.stored_path)
        if source.exists() and audio_path.stat().st_mtime >= source.stat().st_mtime:
            return audio_path
    return extract_audio_wav(Path(video.stored_path), audio_path, sample_rate=16000)


def persist_transcription(
    db: Session,
    video: SourceVideo,
    result: TranscriptionResult,
) -> Transcription:
    # Replace previous transcriptions for the same video+model to keep one active result.
    existing = db.scalars(
        select(Transcription).where(
            Transcription.video_id == video.id,
            Transcription.model_name == result.model_name,
        )
    ).all()
    for row in existing:
        db.delete(row)
    db.flush()

    transcription = Transcription(
        video_id=video.id,
        language=result.language,
        language_probability=result.language_probability,
        model_name=result.model_name,
        full_text=result.full_text,
        segments_json=[
            {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "avg_logprob": seg.avg_logprob,
                "no_speech_prob": seg.no_speech_prob,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "confidence": w.confidence,
                    }
                    for w in seg.words
                ],
            }
            for seg in result.segments
        ],
        audio_path=result.audio_path,
        duration_seconds=result.duration_seconds,
    )
    db.add(transcription)
    db.flush()

    word_rows = [
        TranscriptionWord(
            transcription_id=transcription.id,
            word=word.word,
            start=word.start,
            end=word.end,
            confidence=word.confidence,
            index=index,
        )
        for index, word in enumerate(result.words)
    ]
    db.add_all(word_rows)
    video.status = "transcribed"
    db.commit()
    db.refresh(transcription)
    return transcription


def get_latest_transcription(db: Session, video_id: str) -> Transcription | None:
    return db.scalar(
        select(Transcription)
        .where(Transcription.video_id == video_id)
        .order_by(Transcription.created_at.desc())
        .limit(1)
    )


def get_transcription(db: Session, transcription_id: str) -> Transcription | None:
    return db.scalar(
        select(Transcription)
        .options(selectinload(Transcription.words))
        .where(Transcription.id == transcription_id)
    )


def delete_transcriptions_for_video(db: Session, video_id: str) -> int:
    result = db.execute(delete(Transcription).where(Transcription.video_id == video_id))
    db.commit()
    return int(result.rowcount or 0)


def transcription_to_out(
    transcription: Transcription,
    *,
    include_details: bool = True,
) -> TranscriptionOut:
    segments_raw = transcription.segments_json or []
    words = list(transcription.words or [])
    if include_details and not words and segments_raw:
        # Reconstruct words from segments_json when relationship not loaded.
        flat: list[WordOut] = []
        idx = 0
        for seg in segments_raw:
            for w in seg.get("words", []):
                flat.append(
                    WordOut(
                        word=str(w.get("word", "")),
                        start=float(w.get("start", 0)),
                        end=float(w.get("end", 0)),
                        confidence=w.get("confidence"),
                        index=idx,
                        speaker_label=w.get("speaker_label"),
                    )
                )
                idx += 1
        word_out = flat
    else:
        label_by_index: dict[int, str | None] = {}
        flat_idx = 0
        for seg in segments_raw:
            for w in seg.get("words", []) or []:
                label_by_index[flat_idx] = w.get("speaker_label")
                flat_idx += 1
        word_out = [
            WordOut(
                word=w.word,
                start=w.start,
                end=w.end,
                confidence=w.confidence,
                index=w.index,
                speaker_label=label_by_index.get(w.index),
            )
            for w in sorted(words, key=lambda item: item.index)
        ]

    segments = None
    if include_details:
        segments = [
            SegmentOut(
                id=int(seg.get("id", idx)),
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
                text=str(seg.get("text", "")),
                avg_logprob=seg.get("avg_logprob"),
                no_speech_prob=seg.get("no_speech_prob"),
                speaker_label=seg.get("speaker_label"),
                words=[
                    WordOut(
                        word=str(w.get("word", "")),
                        start=float(w.get("start", 0)),
                        end=float(w.get("end", 0)),
                        confidence=w.get("confidence"),
                        speaker_label=w.get("speaker_label"),
                    )
                    for w in seg.get("words", [])
                ],
            )
            for idx, seg in enumerate(segments_raw)
        ]

    return TranscriptionOut(
        id=transcription.id,
        video_id=transcription.video_id,
        language=transcription.language,
        language_probability=transcription.language_probability,
        model_name=transcription.model_name,
        full_text=transcription.full_text,
        audio_path=transcription.audio_path,
        duration_seconds=transcription.duration_seconds,
        created_at=transcription.created_at,
        segment_count=len(segments_raw),
        word_count=len(word_out),
        segments=segments if include_details else None,
        words=word_out if include_details else None,
    )
