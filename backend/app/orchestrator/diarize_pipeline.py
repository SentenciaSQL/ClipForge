"""Background diarization job runner."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging import get_logger
from app.database.models import ProcessingJob
from app.database.session import SessionLocal
from app.orchestrator.job_manager import job_manager
from app.services.diarization import run_diarization_for_video

logger = get_logger(__name__)


def run_diarize_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job or not job.video_id:
            logger.error("Diarize job %s missing video_id", job_id)
            return
        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        settings = (job.result_json or {}).get("settings") or {}
        job.status = "running"
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.progress = 15.0
        job.current_stage = "diarization"
        job.message = "Running speaker diarization"
        db.commit()

        try:
            result = run_diarization_for_video(
                db,
                job.video_id,
                engine=settings.get("engine"),
                max_speakers=settings.get("max_speakers"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Diarization failed for job %s", job_id)
            job = db.get(ProcessingJob, job_id)
            if not job:
                return
            job.status = "failed"
            job.error = str(exc)
            job.message = "Diarization failed"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
            return

        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        job.status = "completed"
        job.progress = 100.0
        job.current_stage = "diarization"
        job.message = f"Found {len(result.get('speakers') or [])} speakers via {result.get('engine')}"
        job.result_json = {**(job.result_json or {}), **result}
        job.finished_at = datetime.now(timezone.utc)
        job.error = None
        db.commit()
    finally:
        db.close()
        job_manager.clear_cancel(job_id)
