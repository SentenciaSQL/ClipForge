"""Audio Studio endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import AudioTrack, Clip, ProcessingJob
from app.media.http_media import file_response_for_media
from app.orchestrator.job_manager import job_manager
from app.schemas.audio import (
    ApplyAudioPresetRequest,
    AudioMixSettings,
    AudioStudioState,
    AudioTrackCreate,
    AudioTrackOut,
    AudioTrackUpdate,
)
from app.schemas.common import MessageResponse
from app.schemas.jobs import ProcessingJobOut
from app.services import audio_studio as audio_service

router = APIRouter()


class TranscribeTrackRequest(BaseModel):
    language: str | None = None
    whisper_model: str | None = None
    mute_original: bool = Field(
        default=True,
        description="Mute the original track so the uploaded speech drives the mix.",
    )


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


@router.get("/audio-tracks/{track_id}/media")
def stream_audio_track(track_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Stream an uploaded audio track for live Audio Studio A/V preview."""
    track = db.get(AudioTrack, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Audio track not found")
    if not track.source_path:
        raise HTTPException(
            status_code=404,
            detail="Track has no standalone audio file (original audio comes from the video)",
        )
    path = Path(track.source_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")
    download_name = None
    meta = track.metadata_json or {}
    if isinstance(meta, dict) and meta.get("original_filename"):
        download_name = str(meta["original_filename"])
    return file_response_for_media(path, download_name=download_name)


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


@router.post(
    "/clips/{clip_id}/audio-tracks/{track_id}/transcribe-for-subtitles",
    response_model=ProcessingJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def transcribe_track_for_subtitles(
    clip_id: str,
    track_id: str,
    payload: TranscribeTrackRequest | None = None,
    db: Session = Depends(get_db),
) -> ProcessingJobOut:
    """
    Mute original dialogue (optional) and re-transcribe the uploaded track so
    burned-in subtitles match the audio the viewer will hear.
    """
    body = payload or TranscribeTrackRequest()
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    track = db.get(AudioTrack, track_id)
    if not track or track.clip_id != clip.id:
        raise HTTPException(status_code=404, detail="Audio track not found")
    if track.track_type not in {"replacement", "voiceover"}:
        raise HTTPException(
            status_code=400,
            detail="Upload a Replacement or Voice-over track first, then use it for subtitles",
        )
    if not track.source_path:
        raise HTTPException(status_code=400, detail="Track has no audio file")

    if body.mute_original:
        for item in audio_service.list_tracks(db, clip.id):
            if item.track_type == "original" and not item.muted:
                item.muted = True
                item.volume = 0.0
        audio_cfg = dict(clip.audio_config or {})
        audio_cfg["generation_audio_mode"] = (
            "replace" if track.track_type == "replacement" else "voiceover"
        )
        clip.audio_config = audio_cfg
        db.commit()

    job = ProcessingJob(
        project_id=clip.project_id,
        video_id=clip.video_id,
        clip_id=clip.id,
        job_type="clip_audio_transcribe",
        status="queued",
        current_stage="queued",
        progress=0.0,
        message="Queued: transcribe uploaded audio for subtitles",
        stages_json=[
            {"stage": "audio_extraction", "status": "pending"},
            {"stage": "transcription", "status": "pending"},
            {"stage": "subtitle_alignment", "status": "pending"},
        ],
        result_json={
            "settings": {
                "track_id": track.id,
                "language": body.language,
                "whisper_model": body.whisper_model,
                "mute_original": body.mute_original,
            }
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_manager.submit_clip_audio_transcribe(job.id)
    return ProcessingJobOut.model_validate(job)
