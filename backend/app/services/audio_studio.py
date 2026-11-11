"""Audio Studio track management and mix configuration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import AudioPreset, AudioTrack, Clip
from app.media.audio.audio_analyzer import analyze_audio
from app.media.audio.audio_mixer import MixPlan, build_mix_plan
from app.media.audio.audio_tracks import AudioTrackConfig
from app.schemas.audio import AudioMixSettings, AudioTrackCreate, AudioTrackUpdate

logger = get_logger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".mov"}


def _audio_presets_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "resources" / "audio-presets"


def seed_audio_presets(db: Session) -> None:
    preset_dir = _audio_presets_dir()
    if not preset_dir.exists():
        return
    for path in sorted(preset_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping invalid audio preset %s: %s", path.name, exc)
            continue
        name = data.get("name") or path.stem
        existing = db.scalar(select(AudioPreset).where(AudioPreset.name == name))
        if existing:
            existing.config_json = data
        else:
            db.add(AudioPreset(name=name, config_json=data))
    db.commit()


def list_audio_presets(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(AudioPreset).order_by(AudioPreset.name.asc())).all()
    if not rows:
        seed_audio_presets(db)
        rows = db.scalars(select(AudioPreset).order_by(AudioPreset.name.asc())).all()
    return [{"id": row.id, "name": row.name, "slug": (row.config_json or {}).get("slug"), "config": row.config_json} for row in rows]


def default_mix_settings() -> AudioMixSettings:
    return AudioMixSettings()


def get_mix_settings(clip: Clip) -> AudioMixSettings:
    raw = (clip.audio_config or {}).get("mix_settings") if clip.audio_config else None
    if not raw:
        return default_mix_settings()
    try:
        return AudioMixSettings.model_validate(raw)
    except Exception:  # noqa: BLE001
        return default_mix_settings()


def save_mix_settings(db: Session, clip: Clip, settings: AudioMixSettings) -> AudioMixSettings:
    config = dict(clip.audio_config or {})
    config["mix_settings"] = settings.model_dump()
    clip.audio_config = config
    db.commit()
    db.refresh(clip)
    return settings


def ensure_original_track(db: Session, clip: Clip) -> AudioTrack:
    existing = db.scalar(
        select(AudioTrack).where(AudioTrack.clip_id == clip.id, AudioTrack.track_type == "original")
    )
    if existing:
        return existing
    # Honor pre-generation wizard audio intent when first creating the original track.
    mode = ((clip.audio_config or {}).get("generation_audio_mode") or "preserve").lower()
    muted = mode in {"remove", "replace", "music", "voiceover"}
    volume = 0.0 if mode == "remove" else (0.35 if mode in {"music", "voiceover"} else 1.0)
    track = AudioTrack(
        clip_id=clip.id,
        track_type="original",
        label="Original",
        volume=volume,
        muted=muted,
        ducking_enabled=mode in {"music", "voiceover"},
        end_seconds=float(clip.duration_seconds),
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def list_tracks(db: Session, clip_id: str) -> list[AudioTrack]:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ValueError("Clip not found")
    ensure_original_track(db, clip)
    return list(
        db.scalars(
            select(AudioTrack).where(AudioTrack.clip_id == clip_id).order_by(AudioTrack.created_at.asc())
        ).all()
    )


def _clip_audio_dir(clip: Clip) -> Path:
    settings = get_settings()
    path = settings.projects_dir / clip.project_id / "audio" / clip.id
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_track(
    db: Session,
    clip_id: str,
    payload: AudioTrackCreate,
    upload: UploadFile | None = None,
) -> AudioTrack:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ValueError("Clip not found")
    ensure_original_track(db, clip)

    if payload.track_type == "original":
        raise ValueError("Original track is created automatically")

    source_path: str | None = None
    metadata: dict[str, Any] | None = None
    if upload is not None:
        filename = upload.filename or "audio.bin"
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio type: {suffix or 'unknown'}")
        dest = _clip_audio_dir(clip) / f"{payload.track_type}_{Path(filename).stem}{suffix}"
        with dest.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        source_path = str(dest)
        try:
            streams = analyze_audio(dest)
            metadata = {"streams": [s.to_dict() for s in streams], "original_filename": filename}
        except Exception as exc:  # noqa: BLE001
            metadata = {"original_filename": filename, "analyze_error": str(exc)}
    elif payload.track_type in {"music", "voiceover", "replacement"}:
        raise ValueError("Upload an audio file for this track type")

    label = payload.label or payload.track_type.title()
    track = AudioTrack(
        clip_id=clip.id,
        track_type=payload.track_type,
        label=label,
        source_path=source_path,
        volume=payload.volume,
        muted=payload.muted,
        offset_seconds=payload.offset_seconds,
        fade_in_seconds=payload.fade_in_seconds,
        fade_out_seconds=payload.fade_out_seconds,
        loop=payload.loop,
        ducking_enabled=payload.ducking_enabled if payload.track_type == "music" else False,
        end_seconds=float(clip.duration_seconds),
        metadata_json=metadata,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def update_track(db: Session, track_id: str, payload: AudioTrackUpdate) -> AudioTrack:
    track = db.get(AudioTrack, track_id)
    if not track:
        raise ValueError("Track not found")
    data = payload.model_dump(exclude_unset=True)
    if track.track_type != "music":
        data.pop("ducking_enabled", None)
    for key, value in data.items():
        setattr(track, key, value)
    db.commit()
    db.refresh(track)
    return track


def delete_track(db: Session, track_id: str) -> None:
    track = db.get(AudioTrack, track_id)
    if not track:
        raise ValueError("Track not found")
    if track.track_type == "original":
        raise ValueError("Cannot delete the original track; mute it instead")
    source = Path(track.source_path) if track.source_path else None
    db.delete(track)
    db.commit()
    if source and source.exists():
        try:
            source.unlink()
        except OSError:
            pass


def apply_preset(db: Session, clip_id: str, preset_slug: str) -> tuple[Clip, list[AudioTrack], AudioMixSettings]:
    clip = db.get(Clip, clip_id)
    if not clip:
        raise ValueError("Clip not found")
    presets = list_audio_presets(db)
    match = next((p for p in presets if p.get("slug") == preset_slug or p.get("name") == preset_slug), None)
    if not match:
        raise ValueError(f"Audio preset not found: {preset_slug}")
    cfg = match["config"] or {}
    mix = AudioMixSettings(
        enable_loudnorm=bool(cfg.get("enable_loudnorm", True)),
        enable_limiter=bool(cfg.get("enable_limiter", True)),
        integrated_lufs=float(cfg.get("integrated_lufs", -14.0)),
        true_peak=float(cfg.get("true_peak", -1.5)),
        ducking_threshold=float(cfg.get("ducking_threshold", 0.05)),
        ducking_ratio=float(cfg.get("ducking_ratio", 6.0)),
        ducking_attack_ms=float(cfg.get("ducking_attack_ms", 20.0)),
        ducking_release_ms=float(cfg.get("ducking_release_ms", 250.0)),
        preset_slug=cfg.get("slug") or preset_slug,
    )
    save_mix_settings(db, clip, mix)
    tracks = list_tracks(db, clip_id)
    for track in tracks:
        if track.track_type == "original":
            track.volume = float(cfg.get("original_volume", 1.0))
        elif track.track_type == "music":
            track.volume = float(cfg.get("music_volume", 0.35))
            track.ducking_enabled = bool(cfg.get("ducking_enabled", True))
        elif track.track_type == "voiceover":
            track.volume = float(cfg.get("voiceover_volume", 1.0))
    db.commit()
    return clip, list_tracks(db, clip_id), mix


def tracks_to_configs(tracks: list[AudioTrack]) -> list[AudioTrackConfig]:
    configs: list[AudioTrackConfig] = []
    for track in tracks:
        configs.append(
            AudioTrackConfig(
                track_type=track.track_type,  # type: ignore[arg-type]
                label=track.label,
                source_path=track.source_path,
                volume=float(track.volume),
                muted=bool(track.muted),
                start_seconds=float(track.start_seconds or 0.0),
                end_seconds=track.end_seconds,
                offset_seconds=float(track.offset_seconds or 0.0),
                fade_in_seconds=float(track.fade_in_seconds or 0.0),
                fade_out_seconds=float(track.fade_out_seconds or 0.0),
                loop=bool(track.loop),
                ducking_enabled=bool(track.ducking_enabled),
                metadata=track.metadata_json,
            )
        )
    return configs


def build_mix_plan_for_clip(db: Session, clip: Clip) -> MixPlan:
    tracks = list_tracks(db, clip.id)
    configs = tracks_to_configs(tracks)
    # Skip muted-only original still participates with volume 0 so graph stays valid.
    mix = get_mix_settings(clip)
    duck = {
        "threshold": mix.ducking_threshold,
        "ratio": mix.ducking_ratio,
        "attack_ms": mix.ducking_attack_ms,
        "release_ms": mix.ducking_release_ms,
        "integrated_lufs": mix.integrated_lufs,
        "true_peak": mix.true_peak,
        "lra": mix.lra,
    }
    return build_mix_plan(
        0,
        configs,
        enable_loudnorm=mix.enable_loudnorm,
        enable_limiter=mix.enable_limiter,
        ducking=duck,
    )
