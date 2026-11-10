"""Crash recovery: reconcile jobs left running after an unexpected shutdown."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import ProcessingJob
from app.orchestrator.job_manager import job_manager

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def recover_interrupted_jobs(db: Session) -> dict[str, Any]:
    """
    Mark jobs that were mid-flight when the process died.

    Queued/running rows cannot still be executing after a cold start, so they
    become `interrupted` and can be retried via the jobs API.
    """
    stuck = db.scalars(
        select(ProcessingJob).where(ProcessingJob.status.in_(("queued", "running")))
    ).all()
    interrupted_ids: list[str] = []
    for job in stuck:
        previous = job.status
        job.status = "interrupted"
        job.error = f"Recovered after process restart (was {previous})"
        job.message = "Interrupted by application restart — retry available"
        job.finished_at = _utcnow()
        interrupted_ids.append(job.id)
        logger.warning("Marked job %s as interrupted (was %s)", job.id, previous)
    if interrupted_ids:
        db.commit()
    return {"interrupted_count": len(interrupted_ids), "job_ids": interrupted_ids}


def retry_job(db: Session, job_id: str) -> ProcessingJob:
    original = db.get(ProcessingJob, job_id)
    if not original:
        raise ValueError("Job not found")
    if original.status not in {"failed", "cancelled", "interrupted"}:
        raise ValueError(f"Job status '{original.status}' is not retryable")
    if original.job_type in {"analyze", "transcribe", "diarize"} and not original.video_id:
        raise ValueError("Cannot retry this job without video_id")
    if original.job_type == "render" and not original.clip_id:
        raise ValueError("Cannot retry render job without clip_id")
    if original.job_type not in {"analyze", "transcribe", "render", "batch_export", "diarize"}:
        raise ValueError(f"Unsupported job type for retry: {original.job_type}")

    clone = ProcessingJob(
        project_id=original.project_id,
        video_id=original.video_id,
        clip_id=original.clip_id,
        job_type=original.job_type,
        status="queued",
        current_stage="queued",
        progress=0.0,
        message=f"Retry of {original.id}",
        stages_json=_reset_stages(original.stages_json),
        result_json={"settings": (original.result_json or {}).get("settings") or {}, "retry_of": original.id},
        created_at=_utcnow(),
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)

    if clone.job_type in {"analyze", "transcribe"}:
        job_manager.submit_analyze(clone.id)
    elif clone.job_type == "render":
        job_manager.submit_render(clone.id)
    elif clone.job_type == "batch_export":
        job_manager.submit_batch_export(clone.id)
    elif clone.job_type == "diarize":
        job_manager.submit_diarize(clone.id)
    else:
        raise ValueError(f"Unsupported job type for retry: {clone.job_type}")
    return clone


def _reset_stages(stages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not stages:
        return []
    reset: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        item["status"] = "pending"
        item.pop("message", None)
        item.pop("duration_ms", None)
        item.pop("updated_at", None)
        reset.append(item)
    return reset
