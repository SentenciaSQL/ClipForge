"""Dashboard aggregation service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.hardware import detect_hardware
from app.database.models import Clip, ProcessingJob, Project, SourceVideo
from app.schemas.dashboard import DashboardStats
from app.schemas.jobs import ProcessingJobOut
from app.services.projects import list_projects


def get_dashboard_stats(db: Session) -> DashboardStats:
    total_projects = db.scalar(select(func.count()).select_from(Project)) or 0
    imported_videos = db.scalar(select(func.count()).select_from(SourceVideo)) or 0
    generated_clips = db.scalar(select(func.count()).select_from(Clip)) or 0
    active_jobs = db.scalar(
        select(func.count())
        .select_from(ProcessingJob)
        .where(ProcessingJob.status.in_(["queued", "running"]))
    ) or 0

    recent_projects = list_projects(db)[:8]
    jobs = db.scalars(
        select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(10)
    ).all()
    recent_jobs = [ProcessingJobOut.model_validate(job) for job in jobs]

    return DashboardStats(
        total_projects=int(total_projects),
        imported_videos=int(imported_videos),
        generated_clips=int(generated_clips),
        active_jobs=int(active_jobs),
        recent_projects=recent_projects,
        recent_jobs=recent_jobs,
        hardware=detect_hardware().to_dict(),
    )
