"""Background job: transcribe a clip audio track for subtitle alignment."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.gpu_manager import gpu_manager
from app.core.logging import get_logger
from app.database.models import ProcessingJob
from app.database.session import SessionLocal
from app.orchestrator.job_manager import job_manager
from app.services.clip_audio_transcription import transcribe_track_for_subtitles

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_clip_audio_transcribe_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled"
            job.finished_at = _utcnow()
            db.commit()
            return

        settings = (job.result_json or {}).get("settings") or {}
        track_id = settings.get("track_id")
        if not track_id or not job.clip_id:
            job.status = "failed"
            job.error = "Missing clip_id or track_id"
            job.message = "Invalid clip audio transcription job"
            job.finished_at = _utcnow()
            db.commit()
            return

        job.status = "running"
        job.current_stage = "transcription"
        job.progress = 10.0
        job.message = "Transcribing uploaded audio for subtitles"
        job.started_at = job.started_at or _utcnow()
        stages = [
            {"stage": "audio_extraction", "status": "running"},
            {"stage": "transcription", "status": "pending"},
            {"stage": "subtitle_alignment", "status": "pending"},
        ]
        job.stages_json = stages
        db.commit()

        acquired = gpu_manager.acquire("whisper", timeout=3600)
        if not acquired:
            job.status = "failed"
            job.error = "Timed out waiting for GPU lock"
            job.message = "Transcription unavailable"
            job.finished_at = _utcnow()
            db.commit()
            return

        try:
            if job_manager.is_cancelled(job_id):
                job.status = "cancelled"
                job.message = "Cancelled before transcription"
                job.finished_at = _utcnow()
                db.commit()
                return

            job.progress = 35.0
            stages[0]["status"] = "completed"
            stages[1]["status"] = "running"
            job.stages_json = stages
            db.commit()

            summary = transcribe_track_for_subtitles(
                db,
                job.clip_id,
                track_id,
                language=settings.get("language"),
                whisper_model=settings.get("whisper_model"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Clip audio transcription failed for job %s", job_id)
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if not job:
                return
            job.status = "failed"
            job.error = str(exc)
            job.message = f"Failed: {exc}"
            job.finished_at = _utcnow()
            job.stages_json = [
                {"stage": "audio_extraction", "status": "failed"},
                {"stage": "transcription", "status": "failed"},
                {"stage": "subtitle_alignment", "status": "failed"},
            ]
            db.commit()
            return
        finally:
            gpu_manager.release()

        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        job.status = "completed"
        job.progress = 100.0
        job.current_stage = "subtitle_alignment"
        job.message = f"Subtitles aligned to {summary.get('track_type')} audio ({summary.get('segment_count')} segments)"
        job.result_json = {**(job.result_json or {}), "result": summary}
        job.finished_at = _utcnow()
        job.stages_json = [
            {"stage": "audio_extraction", "status": "completed"},
            {"stage": "transcription", "status": "completed"},
            {"stage": "subtitle_alignment", "status": "completed"},
        ]
        db.commit()
    finally:
        db.close()
