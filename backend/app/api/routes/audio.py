"""Audio Studio endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import Clip
from app.schemas.audio import (
    ApplyAudioPresetRequest,
    AudioMixSettings,
    AudioStudioState,
    AudioTrackCreate,
    AudioTrackOut,
    AudioTrackUpdate,
)
from app.schemas.common import MessageResponse
from app.services import audio_studio as audio_service

router = APIRouter()


def _track_out(track) -> AudioTrackOut:
    return AudioTrackOut.model_validate(track)


@router.get("/clips/{clip_id}/audio", response_model=AudioStudioState)
def get_audio_studio(clip_id: str, db: Session = Depends(get_db)) -> AudioStudioState:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    tracks = audio_service.list_tracks(db, clip_id)
    return AudioStudioState(
        clip_id=clip.id,
        duration_seconds=float(clip.duration_seconds),
        tracks=[_track_out(t) for t in tracks],
        mix_settings=audio_service.get_mix_settings(clip),
        audio_presets=audio_service.list_audio_presets(db),
    )


@router.get("/audio-presets")
def list_presets(db: Session = Depends(get_db)) -> list[dict]:
    return audio_service.list_audio_presets(db)


@router.put("/clips/{clip_id}/audio/mix-settings", response_model=AudioMixSettings)
def update_mix_settings(
    clip_id: str,
    payload: AudioMixSettings,
    db: Session = Depends(get_db),
) -> AudioMixSettings:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return audio_service.save_mix_settings(db, clip, payload)


@router.post("/clips/{clip_id}/audio/apply-preset", response_model=AudioStudioState)
def apply_preset(
    clip_id: str,
    payload: ApplyAudioPresetRequest,
    db: Session = Depends(get_db),
) -> AudioStudioState:
    try:
        clip, tracks, mix = audio_service.apply_preset(db, clip_id, payload.preset_slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AudioStudioState(
        clip_id=clip.id,
        duration_seconds=float(clip.duration_seconds),
        tracks=[_track_out(t) for t in tracks],
        mix_settings=mix,
        audio_presets=audio_service.list_audio_presets(db),
    )


@router.get("/clips/{clip_id}/audio-tracks", response_model=list[AudioTrackOut])
def list_tracks(clip_id: str, db: Session = Depends(get_db)) -> list[AudioTrackOut]:
    try:
        tracks = audio_service.list_tracks(db, clip_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_track_out(t) for t in tracks]


@router.post(
    "/clips/{clip_id}/audio-tracks",
    response_model=AudioTrackOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_track(
    clip_id: str,
    track_type: str = Form(...),
    label: str | None = Form(None),
    volume: float = Form(1.0),
    muted: bool = Form(False),
    offset_seconds: float = Form(0.0),
    fade_in_seconds: float = Form(0.0),
    fade_out_seconds: float = Form(0.0),
    ducking_enabled: bool = Form(False),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
) -> AudioTrackOut:
    payload = AudioTrackCreate(
        track_type=track_type,  # type: ignore[arg-type]
        label=label,
        volume=volume,
        muted=muted,
        offset_seconds=offset_seconds,
        fade_in_seconds=fade_in_seconds,
        fade_out_seconds=fade_out_seconds,
        ducking_enabled=ducking_enabled,
    )
    try:
        track = audio_service.create_track(db, clip_id, payload, upload=file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _track_out(track)


@router.patch("/audio-tracks/{track_id}", response_model=AudioTrackOut)
def patch_track(
    track_id: str,
    payload: AudioTrackUpdate,
    db: Session = Depends(get_db),
) -> AudioTrackOut:
    try:
        track = audio_service.update_track(db, track_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _track_out(track)


@router.delete("/audio-tracks/{track_id}", response_model=MessageResponse)
def remove_track(track_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        audio_service.delete_track(db, track_id)
    except ValueError as exc:
        status_code = 400 if "Cannot delete" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return MessageResponse(message="Track deleted")
