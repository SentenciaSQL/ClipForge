"""Processing job endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import ProcessingJob
from app.orchestrator.job_manager import job_manager
from app.schemas.common import MessageResponse
from app.schemas.jobs import ProcessingJobOut

router = APIRouter()


@router.get("/jobs", response_model=list[ProcessingJobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[ProcessingJobOut]:
    jobs = db.scalars(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(100)).all()
    return [ProcessingJobOut.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: str, db: Session = Depends(get_db)) -> ProcessingJobOut:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ProcessingJobOut.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=MessageResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in {"completed", "failed", "cancelled"}:
        return MessageResponse(message=f"Job already {job.status}")

    job_manager.request_cancel(job_id)
    if job.status == "queued":
        job.status = "cancelled"
        job.message = "Cancelled while queued"
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    else:
        job.message = "Cancellation requested"
        db.commit()
    return MessageResponse(message="Cancellation requested")
