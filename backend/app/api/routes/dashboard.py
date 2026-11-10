"""Dashboard stats endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dashboard import DashboardStats
from app.services.dashboard import get_dashboard_stats

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)) -> DashboardStats:
    return get_dashboard_stats(db)
