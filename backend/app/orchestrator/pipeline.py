"""Analysis pipeline stages for Phase 2 (through transcription)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.ai.transcription.whisper_service import whisper_service
from app.core.logging import get_logger
from app.database.models import ProcessingJob, SourceVideo
from app.database.session import SessionLocal
from app.orchestrator.job_manager import job_manager
from app.services.transcriptions import extract_audio_for_video, persist_transcription

logger = get_logger(__name__)

ProgressCallback = Callable[[str, float, str, dict[str, Any] | None], None]

PHASE2_TERMINAL_STAGES = {
    "semantic_analysis",
    "highlight_selection",
    "visual_analysis",
    "subtitle_generation",
    "rendering",
    "export",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _update_stage_list(
    stages: list[dict[str, Any]],
    stage_name: str,
    status: str,
    *,
    message: str | None = None,
    duration_ms: int | None = None,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    found = False
    for stage in stages:
        item = dict(stage)
        if item.get("stage") == stage_name:
            found = True
            item["status"] = status
            if message is not None:
                item["message"] = message
            if duration_ms is not None:
                item["duration_ms"] = duration_ms
            item["updated_at"] = _utcnow().isoformat()
        updated.append(item)
    if not found:
        updated.append(
            {
                "stage": stage_name,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "updated_at": _utcnow().isoformat(),
            }
        )
    return updated


def _set_deferred_later_stages(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        if item.get("stage") in PHASE2_TERMINAL_STAGES and item.get("status") == "pending":
            item["status"] = "deferred"
            item["message"] = "Scheduled for a later phase"
        result.append(item)
    return result


def run_phase2_analyze_job(job_id: str) -> None:
    """Execute audio extraction + transcription for an analyze job."""
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job or not job.video_id:
            logger.error("Job %s missing or has no video_id", job_id)
            return

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled before start"
            job.finished_at = _utcnow()
            db.commit()
            return

        video = db.get(SourceVideo, job.video_id)
        if not video:
            job.status = "failed"
            job.error = f"Video not found: {job.video_id}"
            job.finished_at = _utcnow()
            db.commit()
            return

        settings = (job.result_json or {}).get("settings") or {}
        language = settings.get("language")
        whisper_model = settings.get("whisper_model")
        force = bool(settings.get("force", False))

        stages = list(job.stages_json or [])
        job.status = "running"
        job.started_at = job.started_at or _utcnow()
        job.current_stage = "audio_extraction"
        job.progress = 10.0
        job.message = "Extracting audio with FFmpeg"
        stages = _update_stage_list(stages, "audio_extraction", "running")
        job.stages_json = stages
        db.commit()

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled during audio extraction"
            job.finished_at = _utcnow()
            db.commit()
            return

        started = time.perf_counter()
        try:
            audio_path = extract_audio_for_video(video)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio extraction failed for job %s", job_id)
            stages = _update_stage_list(
                stages,
                "audio_extraction",
                "failed",
                message=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            job.stages_json = stages
            job.status = "failed"
            job.error = f"Audio extraction failed: {exc}"
            job.current_stage = "audio_extraction"
            job.finished_at = _utcnow()
            db.commit()
            return

        audio_ms = int((time.perf_counter() - started) * 1000)
        stages = _update_stage_list(
            stages,
            "audio_extraction",
            "completed",
            message=str(audio_path),
            duration_ms=audio_ms,
        )
        job.stages_json = stages
        job.progress = 35.0
        job.current_stage = "transcription"
        job.message = "Transcribing with Faster-Whisper"
        stages = _update_stage_list(stages, "transcription", "running")
        job.stages_json = stages
        db.commit()

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled before transcription"
            job.finished_at = _utcnow()
            db.commit()
            return

        started = time.perf_counter()
        acquired = job_manager.gpu_lock.acquire(timeout=3600)
        if not acquired:
            job.status = "failed"
            job.error = "Timed out waiting for GPU lock"
            job.finished_at = _utcnow()
            db.commit()
            return

        try:
            result = whisper_service.transcribe(
                Path(audio_path),
                video_id=video.id,
                model_name=whisper_model,
                language=language or None,
                use_cache=not force,
            )
            transcription = persist_transcription(db, video, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Transcription failed for job %s", job_id)
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if not job:
                return
            stages = list(job.stages_json or [])
            stages = _update_stage_list(
                stages,
                "transcription",
                "failed",
                message=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            job.stages_json = stages
            job.status = "failed"
            job.error = f"Transcription failed: {exc}"
            job.current_stage = "transcription"
            job.finished_at = _utcnow()
            db.commit()
            return
        finally:
            job_manager.gpu_lock.release()

        # persist_transcription commits and may expire instances; reload job.
        job = db.get(ProcessingJob, job_id)
        video = db.get(SourceVideo, video.id)
        if not job:
            return

        tx_ms = int((time.perf_counter() - started) * 1000)
        stages = list(job.stages_json or [])
        stages = _update_stage_list(
            stages,
            "transcription",
            "completed",
            message=f"language={result.language} words={len(result.words)}",
            duration_ms=tx_ms,
        )
        stages = _set_deferred_later_stages(stages)
        job.stages_json = stages
        job.progress = 100.0
        job.status = "completed"
        job.current_stage = "transcription"
        job.message = (
            f"Phase 2 complete: transcribed ({result.language or 'unknown'}), "
            f"{len(result.words)} words. Later stages deferred."
        )
        job.error = None
        job.finished_at = _utcnow()
        job.result_json = {
            **(job.result_json or {}),
            "transcription_id": transcription.id,
            "language": result.language,
            "language_probability": result.language_probability,
            "model_name": result.model_name,
            "device": result.device,
            "word_count": len(result.words),
            "segment_count": len(result.segments),
            "audio_path": result.audio_path,
            "full_text_preview": (result.full_text or "")[:500],
        }
        db.commit()
        logger.info("Job %s completed transcription %s", job_id, transcription.id)
    finally:
        db.close()
        job_manager.clear_cancel(job_id)
