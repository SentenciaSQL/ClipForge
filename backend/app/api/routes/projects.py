"""Project CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.common import MessageResponse
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate
from app.schemas.videos import SourceVideoOut
from app.services import projects as project_service
from app.services.videos import list_videos, video_to_out

router = APIRouter()


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    return project_service.create_project(db, payload)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    return project_service.list_projects(db)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> ProjectOut:
    project = project_service.update_project(db, project_id, payload)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/projects/{project_id}", response_model=MessageResponse)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    deleted = project_service.delete_project(db, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return MessageResponse(message="Project deleted")


@router.get("/projects/{project_id}/videos", response_model=list[SourceVideoOut])
def project_videos(project_id: str, db: Session = Depends(get_db)) -> list[SourceVideoOut]:
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return [video_to_out(video) for video in list_videos(db, project_id)]


@router.get("/projects/{project_id}/clips")
def project_clips(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """Phase 1 placeholder — clips are produced in later phases."""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return []
