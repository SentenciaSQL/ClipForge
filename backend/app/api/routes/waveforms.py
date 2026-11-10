"""Waveform peak endpoints for Audio Studio timelines."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database.models import Clip, SourceVideo
from app.media.audio.waveform import compute_peaks
from app.services.audio_studio import list_tracks
from app.services.transcriptions import extract_audio_for_video

router = APIRouter()


@router.get("/clips/{clip_id}/waveforms")
def clip_waveforms(
    clip_id: str,
    num_peaks: int = Query(default=480, ge=64, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    video = db.get(SourceVideo, clip.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Source video missing")

    tracks = list_tracks(db, clip_id)
    waveforms: list[dict] = []
    for track in tracks:
        try:
            if track.track_type == "original":
                audio_path = extract_audio_for_video(video)
                peaks = compute_peaks(
                    audio_path,
                    start_seconds=float(clip.start_seconds),
                    duration_seconds=float(clip.duration_seconds),
                    num_peaks=num_peaks,
                )
            elif track.source_path and Path(track.source_path).exists():
                peaks = compute_peaks(
                    track.source_path,
                    start_seconds=0.0,
                    duration_seconds=float(clip.duration_seconds),
                    num_peaks=num_peaks,
                )
            else:
                peaks = {
                    "peaks": [0.0] * num_peaks,
                    "sample_rate": 0,
                    "start_seconds": 0.0,
                    "duration_seconds": float(clip.duration_seconds),
                    "path": track.source_path,
                }
        except Exception as exc:  # noqa: BLE001
            peaks = {
                "peaks": [0.0] * num_peaks,
                "error": str(exc),
                "path": track.source_path,
                "duration_seconds": float(clip.duration_seconds),
            }
        waveforms.append(
            {
                "track_id": track.id,
                "track_type": track.track_type,
                "label": track.label,
                "muted": track.muted,
                "volume": track.volume,
                "ducking_enabled": track.ducking_enabled,
                **peaks,
            }
        )

    return {
        "clip_id": clip.id,
        "duration_seconds": float(clip.duration_seconds),
        "start_seconds": float(clip.start_seconds),
        "end_seconds": float(clip.end_seconds),
        "waveforms": waveforms,
    }
