"""Project CRUD service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Clip, Project, SourceVideo
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate


def _to_out(db: Session, project: Project) -> ProjectOut:
    video_count = db.scalar(
        select(func.count()).select_from(SourceVideo).where(SourceVideo.project_id == project.id)
    ) or 0
    clip_count = db.scalar(
        select(func.count()).select_from(Clip).where(Clip.project_id == project.id)
    ) or 0
    return ProjectOut(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        video_count=int(video_count),
        clip_count=int(clip_count),
    )


def create_project(db: Session, payload: ProjectCreate) -> ProjectOut:
    project = Project(name=payload.name.strip(), description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(db, project)


def list_projects(db: Session) -> list[ProjectOut]:
    projects = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
    return [_to_out(db, project) for project in projects]


def get_project(db: Session, project_id: str) -> ProjectOut | None:
    project = db.get(Project, project_id)
    if not project:
        return None
    return _to_out(db, project)


def update_project(db: Session, project_id: str, payload: ProjectUpdate) -> ProjectOut | None:
    project = db.get(Project, project_id)
    if not project:
        return None
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return _to_out(db, project)


def delete_project(db: Session, project_id: str) -> bool:
    project = db.get(Project, project_id)
    if not project:
        return False
    db.delete(project)
    db.commit()
    return True
