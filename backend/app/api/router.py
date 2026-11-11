"""Aggregate API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    audio,
    clip_config,
    clips,
    dashboard,
    diarization,
    export_profiles,
    generation,
    health,
    highlights,
    jobs,
    presets,
    projects,
    settings,
    system,
    transcriptions,
    videos,
    waveforms,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(videos.router, tags=["videos"])
api_router.include_router(generation.router, tags=["generation"])
api_router.include_router(transcriptions.router, tags=["transcriptions"])
api_router.include_router(highlights.router, tags=["highlights"])
api_router.include_router(clips.router, tags=["clips"])
api_router.include_router(clip_config.router, tags=["clip-configuration"])
api_router.include_router(export_profiles.router, tags=["export-profiles"])
api_router.include_router(audio.router, tags=["audio"])
api_router.include_router(waveforms.router, tags=["waveforms"])
api_router.include_router(diarization.router, tags=["diarization"])
api_router.include_router(presets.router, tags=["presets"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(settings.router, tags=["settings"])
