"""Background render / batch-export job runners."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.database.models import ProcessingJob
from app.database.session import SessionLocal
from app.orchestrator.job_manager import job_manager
from app.services.rendering import export_clips, render_clip_asset

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _update_stage(
    stages: list[dict[str, Any]],
    name: str,
    status: str,
    *,
    message: str | None = None,
    duration_ms: int | None = None,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    found = False
    for stage in stages:
        item = dict(stage)
        if item.get("stage") == name:
            found = True
            item["status"] = status
            if message is not None:
                item["message"] = message
            if duration_ms is not None:
                item["duration_ms"] = duration_ms
            item["updated_at"] = _utcnow().isoformat()
        updated.append(item)
    if not found:
        updated.append(
            {
                "stage": name,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "updated_at": _utcnow().isoformat(),
            }
        )
    return updated


def run_render_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job or not job.clip_id:
            logger.error("Render job %s missing clip_id", job_id)
            return
        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.finished_at = _utcnow()
            db.commit()
            return

        settings = (job.result_json or {}).get("settings") or {}
        stages = list(job.stages_json or [])
        job.status = "running"
        job.started_at = job.started_at or _utcnow()
        job.progress = 10.0
        job.current_stage = "subtitle_generation"
        job.message = "Generating ASS subtitles"
        stages = _update_stage(stages, "subtitle_generation", "running")
        job.stages_json = stages
        db.commit()

        started = time.perf_counter()
        try:
            # Subtitle generation + reframe + encode happen inside render_clip_asset.
            job.progress = 35.0
            job.current_stage = "visual_analysis"
            job.message = "Planning vertical reframing"
            stages = _update_stage(stages, "subtitle_generation", "completed")
            stages = _update_stage(stages, "visual_analysis", "running")
            job.stages_json = stages
            db.commit()

            job.progress = 55.0
            job.current_stage = "rendering"
            job.message = "Rendering clip with FFmpeg"
            stages = _update_stage(stages, "visual_analysis", "completed")
            stages = _update_stage(stages, "rendering", "running")
            job.stages_json = stages
            db.commit()

            clip = render_clip_asset(
                db,
                job.clip_id,
                reframing_mode=settings.get("reframing_mode"),
                subtitle_preset=settings.get("subtitle_preset"),
                burn_subtitles=bool(settings.get("burn_subtitles", True)),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Render failed for job %s", job_id)
            job = db.get(ProcessingJob, job_id)
            if not job:
                return
            stages = list(job.stages_json or [])
            stages = _update_stage(
                stages,
                job.current_stage or "rendering",
                "failed",
                message=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            job.stages_json = stages
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = _utcnow()
            db.commit()
            return

        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        stages = list(job.stages_json or [])
        elapsed = int((time.perf_counter() - started) * 1000)
        stages = _update_stage(stages, "rendering", "completed", message=clip.output_path, duration_ms=elapsed)
        stages = _update_stage(stages, "export", "completed", message=clip.output_path)
        job.stages_json = stages
        job.progress = 100.0
        job.status = "completed"
        job.current_stage = "export"
        job.message = f"Rendered clip → {clip.output_path}"
        job.error = None
        job.finished_at = _utcnow()
        job.result_json = {
            **(job.result_json or {}),
            "output_path": clip.output_path,
            "ass_path": clip.ass_path,
            "render_settings": clip.render_settings,
        }
        db.commit()
    finally:
        db.close()
        job_manager.clear_cancel(job_id)


def run_batch_export_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        settings = (job.result_json or {}).get("settings") or {}
        clip_ids = list(settings.get("clip_ids") or [])
        stages = list(job.stages_json or [])
        job.status = "running"
        job.started_at = job.started_at or _utcnow()
        job.current_stage = "export"
        job.progress = 5.0
        job.message = f"Exporting {len(clip_ids)} clips"
        stages = _update_stage(stages, "export", "running")
        job.stages_json = stages
        db.commit()

        exported_paths: list[str] = []
        for index, clip_id in enumerate(clip_ids, start=1):
            if job_manager.is_cancelled(job_id):
                job.status = "cancelled"
                job.finished_at = _utcnow()
                db.commit()
                return
            try:
                paths = export_clips(db, [clip_id])
                exported_paths.extend(str(path) for path in paths)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Batch export failed for clip %s", clip_id)
                job.error = str(exc)
                job.status = "failed"
                job.finished_at = _utcnow()
                stages = _update_stage(stages, "export", "failed", message=str(exc))
                job.stages_json = stages
                db.commit()
                return
            job.progress = min(99.0, (index / max(len(clip_ids), 1)) * 100.0)
            job.message = f"Exported {index}/{len(clip_ids)}"
            db.commit()

        stages = _update_stage(stages, "export", "completed", message=f"{len(exported_paths)} files")
        job.stages_json = stages
        job.progress = 100.0
        job.status = "completed"
        job.message = f"Exported {len(exported_paths)} clips"
        job.finished_at = _utcnow()
        job.result_json = {**(job.result_json or {}), "exported_paths": exported_paths}
        db.commit()
    finally:
        db.close()
        job_manager.clear_cancel(job_id)
