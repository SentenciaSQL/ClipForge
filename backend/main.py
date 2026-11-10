"""AI Video Clipper — FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.api.routes.ws import router as ws_router
from app.core.config import get_settings
from app.core.hardware import detect_hardware
from app.core.logging import configure_logging, get_logger
from app.database.session import SessionLocal, init_db
from app.orchestrator.job_manager import job_manager
from app.services.audio_studio import seed_audio_presets
from app.services.seed import seed_subtitle_presets

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    settings.ensure_directories()
    init_db()
    db = SessionLocal()
    try:
        seed_subtitle_presets(db)
        seed_audio_presets(db)
    finally:
        db.close()
    hardware = detect_hardware()
    logger.info("AI Video Clipper backend v%s ready", __version__)
    logger.info(
        "Hardware: device=%s ffmpeg=%s cuda=%s ollama=%s",
        hardware.recommended_device,
        hardware.ffmpeg_available,
        hardware.cuda_available,
        hardware.ollama_available,
    )
    for note in hardware.notes:
        logger.warning("Hardware note: %s", note)
    yield
    job_manager.shutdown(wait=False)
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI Video Clipper API",
        version=__version__,
        description="Fully local AI-powered video clipping platform",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    application.include_router(ws_router)
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cfg = get_settings()
    uvicorn.run(
        "main:app",
        host=cfg.host,
        port=cfg.port,
        reload=cfg.debug,
    )
