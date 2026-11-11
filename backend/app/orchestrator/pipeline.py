"""Analysis pipeline stages through Phase 3 highlight selection."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.ai.highlights.analyzer import highlight_analyzer
from app.ai.llm.ollama_client import OllamaError
from app.core.gpu_manager import gpu_manager
from app.ai.transcription.whisper_service import whisper_service
from app.core.logging import get_logger
from app.database.models import ProcessingJob, SourceVideo, Transcription
from app.database.session import SessionLocal
from app.orchestrator.job_manager import job_manager
from app.services.highlights import persist_highlights
from app.services.transcriptions import extract_audio_for_video, get_latest_transcription, persist_transcription

logger = get_logger(__name__)

PHASE3_DEFERRED_STAGES = {
    "visual_analysis",
    "subtitle_generation",
    "rendering",
    "export",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _update_stage_list(
    stages: list[dict[str, Any]],
    stage_name: str,
    status: str,
    *,
    message: str | None = None,
    duration_ms: int | None = None,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    found = False
    for stage in stages:
        item = dict(stage)
        if item.get("stage") == stage_name:
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
                "stage": stage_name,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "updated_at": _utcnow().isoformat(),
            }
        )
    return updated


def _set_deferred_later_stages(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for stage in stages:
        item = dict(stage)
        if item.get("stage") in PHASE3_DEFERRED_STAGES and item.get("status") in {"pending", "deferred"}:
            item["status"] = "deferred"
            item["message"] = "Scheduled for a later phase"
        result.append(item)
    return result


def _fail_job(
    db,
    job: ProcessingJob,
    stages: list[dict[str, Any]],
    stage: str,
    error: str,
    started: float,
) -> None:
    stages = _update_stage_list(
        stages,
        stage,
        "failed",
        message=error,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    job.stages_json = stages
    job.status = "failed"
    job.error = error
    job.current_stage = stage
    job.finished_at = _utcnow()
    db.commit()


def run_phase2_analyze_job(job_id: str) -> None:
    """Backward-compatible entrypoint name used by JobManager."""
    run_analyze_job(job_id)


def run_analyze_job(job_id: str) -> None:
    """Execute audio → transcription → semantic analysis → highlight selection."""
    db = SessionLocal()
    try:
        job = db.get(ProcessingJob, job_id)
        if not job or not job.video_id:
            logger.error("Job %s missing or has no video_id", job_id)
            return

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled before start"
            job.finished_at = _utcnow()
            db.commit()
            return

        video = db.get(SourceVideo, job.video_id)
        if not video:
            job.status = "failed"
            job.error = f"Video not found: {job.video_id}"
            job.finished_at = _utcnow()
            db.commit()
            return

        settings = (job.result_json or {}).get("settings") or {}
        language = settings.get("language")
        whisper_model = settings.get("whisper_model")
        force = bool(settings.get("force", False))
        clip_count = int(settings.get("clip_count") or 5)
        min_duration = int(settings.get("min_duration") or 12)
        max_duration = int(settings.get("max_duration") or 30)
        ollama_model = settings.get("ollama_model")
        subtitle_preset = settings.get("subtitle_preset") or "hormozi"
        content_category = settings.get("content_category") or "auto"
        if settings.get("auto_detect_content_type"):
            content_category = "auto"

        stages = list(job.stages_json or [])
        job.status = "running"
        job.started_at = job.started_at or _utcnow()
        job.error = None

        # -------- Stage: audio extraction --------
        job.current_stage = "audio_extraction"
        job.progress = 8.0
        job.message = "Extracting audio with FFmpeg"
        stages = _update_stage_list(stages, "audio_extraction", "running")
        job.stages_json = stages
        db.commit()

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled during audio extraction"
            job.finished_at = _utcnow()
            db.commit()
            return

        started = time.perf_counter()
        try:
            audio_path = extract_audio_for_video(video)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Audio extraction failed for job %s", job_id)
            _fail_job(db, job, stages, "audio_extraction", f"Audio extraction failed: {exc}", started)
            return

        stages = _update_stage_list(
            stages,
            "audio_extraction",
            "completed",
            message=str(audio_path),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        job.stages_json = stages
        db.commit()

        # -------- Stage: transcription --------
        job.progress = 25.0
        job.current_stage = "transcription"
        job.message = "Transcribing with Faster-Whisper"
        stages = _update_stage_list(stages, "transcription", "running")
        job.stages_json = stages
        db.commit()

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled before transcription"
            job.finished_at = _utcnow()
            db.commit()
            return

        started = time.perf_counter()
        transcription: Transcription | None = None
        if not force:
            transcription = get_latest_transcription(db, video.id)

        if transcription is None:
            if force:
                from app.services.cache_service import invalidate_transcription_cache

                invalidate_transcription_cache(video.id)
            acquired = gpu_manager.acquire("whisper", timeout=3600)
            if not acquired:
                _fail_job(db, job, stages, "transcription", "Timed out waiting for GPU lock", started)
                return
            try:
                result = whisper_service.transcribe(
                    Path(audio_path),
                    video_id=video.id,
                    model_name=whisper_model,
                    language=language or None,
                    use_cache=not force,
                )
                transcription = persist_transcription(db, video, result)
                tx_meta = {
                    "language": result.language,
                    "language_probability": result.language_probability,
                    "model_name": result.model_name,
                    "device": result.device,
                    "word_count": len(result.words),
                    "segment_count": len(result.segments),
                    "audio_path": result.audio_path,
                    "full_text_preview": (result.full_text or "")[:500],
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("Transcription failed for job %s", job_id)
                db.rollback()
                job = db.get(ProcessingJob, job_id)
                if not job:
                    return
                stages = list(job.stages_json or [])
                _fail_job(db, job, stages, "transcription", f"Transcription failed: {exc}", started)
                return
            finally:
                # Free Whisper VRAM before Ollama takes the GPU.
                gpu_manager.prepare_for_llm()
                gpu_manager.release()
        else:
            tx_meta = {
                "language": transcription.language,
                "language_probability": transcription.language_probability,
                "model_name": transcription.model_name,
                "word_count": len(transcription.segments_json or []),
                "segment_count": len(transcription.segments_json or []),
                "audio_path": transcription.audio_path,
                "full_text_preview": (transcription.full_text or "")[:500],
                "reused_existing": True,
            }

        job = db.get(ProcessingJob, job_id)
        video = db.get(SourceVideo, video.id)
        transcription = db.get(Transcription, transcription.id) if transcription else None
        if not job or not video or not transcription:
            return

        stages = list(job.stages_json or [])
        stages = _update_stage_list(
            stages,
            "transcription",
            "completed",
            message=f"language={transcription.language}",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        job.stages_json = stages
        job.result_json = {**(job.result_json or {}), "transcription_id": transcription.id, **tx_meta}
        db.commit()

        # -------- Stage: semantic analysis + highlight selection --------
        job.progress = 55.0
        job.current_stage = "semantic_analysis"
        job.message = "Analyzing transcript with local Ollama model"
        stages = _update_stage_list(stages, "semantic_analysis", "running")
        job.stages_json = stages
        db.commit()

        if job_manager.is_cancelled(job_id):
            job.status = "cancelled"
            job.message = "Cancelled before semantic analysis"
            job.finished_at = _utcnow()
            db.commit()
            return

        started = time.perf_counter()
        segments = list(transcription.segments_json or [])
        gpu_manager.prepare_for_llm()
        acquired = gpu_manager.acquire("ollama", timeout=3600)
        if not acquired:
            _fail_job(db, job, stages, "semantic_analysis", "Timed out waiting for GPU/LLM lock", started)
            return

        try:
            selected = highlight_analyzer.analyze_transcription(
                segments,
                model=ollama_model,
                clip_count=clip_count,
                min_seconds=min_duration,
                max_seconds=max_duration,
                video_duration=video.duration_seconds,
                content_category=str(content_category),
            )
            # analyzer already returns selected/distinct; keep a scored pool = selected for persistence rank.
            raw_pool = list(selected)
        except OllamaError as exc:
            logger.exception("Semantic analysis failed for job %s", job_id)
            _fail_job(db, job, stages, "semantic_analysis", str(exc), started)
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Semantic analysis failed for job %s", job_id)
            _fail_job(db, job, stages, "semantic_analysis", f"Semantic analysis failed: {exc}", started)
            return
        finally:
            gpu_manager.release()

        job = db.get(ProcessingJob, job_id)
        video = db.get(SourceVideo, video.id)
        if not job or not video:
            return
        stages = list(job.stages_json or [])
        stages = _update_stage_list(
            stages,
            "semantic_analysis",
            "completed",
            message=f"candidates={len(raw_pool)}",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        job.stages_json = stages
        job.progress = 80.0
        job.current_stage = "highlight_selection"
        job.message = "Selecting distinct 12–30s highlights"
        stages = _update_stage_list(stages, "highlight_selection", "running")
        job.stages_json = stages
        db.commit()

        started = time.perf_counter()
        try:
            # Re-run selection is already done; persist selected + same pool.
            highlights, clips = persist_highlights(
                db,
                video,
                candidates=raw_pool,
                selected=selected,
                subtitle_preset_slug=subtitle_preset,
                reframing_mode=str(settings.get("reframing_mode") or "auto"),
            )
            # Inherit the pre-generation wizard configuration onto every clip.
            from app.schemas.generation_config import GenerationConfiguration
            from app.services.generation_config import apply_generation_config_to_clips

            raw_gen = settings.get("generation_config")
            gen_cfg = None
            if isinstance(raw_gen, dict):
                try:
                    gen_cfg = GenerationConfiguration.model_validate(raw_gen)
                except Exception:  # noqa: BLE001
                    gen_cfg = None
            apply_generation_config_to_clips(db, video, clips, gen_cfg)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Highlight persistence failed for job %s", job_id)
            db.rollback()
            job = db.get(ProcessingJob, job_id)
            if not job:
                return
            stages = list(job.stages_json or [])
            _fail_job(db, job, stages, "highlight_selection", f"Highlight selection failed: {exc}", started)
            return

        job = db.get(ProcessingJob, job_id)
        if not job:
            return
        stages = list(job.stages_json or [])
        stages = _update_stage_list(
            stages,
            "highlight_selection",
            "completed",
            message=f"selected={len(clips)} highlights={len(highlights)}",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        stages = _set_deferred_later_stages(stages)
        job.stages_json = stages
        job.progress = 100.0
        job.status = "completed"
        job.current_stage = "highlight_selection"
        job.message = (
            f"Phase 3 complete: {len(clips)} clips selected from local semantic analysis. "
            "Rendering deferred."
        )
        job.error = None
        job.finished_at = _utcnow()
        job.result_json = {
            **(job.result_json or {}),
            "highlight_count": len(highlights),
            "selected_clip_count": len(clips),
            "clips": [
                {
                    "id": clip.id,
                    "hook": clip.hook,
                    "score": clip.score,
                    "start_seconds": clip.start_seconds,
                    "end_seconds": clip.end_seconds,
                    "category": clip.category,
                }
                for clip in clips
            ],
        }
        db.commit()
        logger.info("Job %s completed with %s clips", job_id, len(clips))
    finally:
        db.close()
        job_manager.clear_cancel(job_id)
