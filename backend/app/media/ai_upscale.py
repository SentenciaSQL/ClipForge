"""Optional local AI upscaling (Real-ESRGAN / ncnn). Never required for render."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AiUpscaleStatus:
    available: bool
    engine: str | None
    message: str
    warning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "engine": self.engine,
            "message": self.message,
            "warning": self.warning,
        }


DEFAULT_WARNING = (
    "AI upscaling cannot perfectly reconstruct missing detail from low-resolution sources. "
    "It may improve perceived sharpness but can invent textures. Keep VRAM free — do not load "
    "Whisper/Ollama simultaneously with a heavy upscaler."
)


def detect_ai_upscaler() -> AiUpscaleStatus:
    """Detect a locally installed CLI upscaler without loading models into VRAM."""
    for binary, name in (
        ("realesrgan-ncnn-vulkan", "Real-ESRGAN (ncnn-vulkan)"),
        ("realesrgan-ncnn-vulkan.exe", "Real-ESRGAN (ncnn-vulkan)"),
        ("realesrgan-ncnn", "Real-ESRGAN (ncnn)"),
    ):
        path = shutil.which(binary)
        if path:
            return AiUpscaleStatus(
                available=True,
                engine=name,
                message=f"Found local upscaler at {path}",
                warning=DEFAULT_WARNING,
            )
    return AiUpscaleStatus(
        available=False,
        engine=None,
        message=(
            "No local AI upscaler detected. Install realesrgan-ncnn-vulkan on PATH to enable "
            "optional upscaling. Standard Lanczos scaling remains the default."
        ),
        warning=DEFAULT_WARNING,
    )


def apply_ai_upscale_if_requested(*, enabled: bool) -> dict[str, Any]:
    """
    Gate for future per-frame upscale integration.

    Current render path uses high-quality Lanczos inside the single FFmpeg graph.
    When enabled but no engine is installed, callers must fall back without failing the job.
    """
    status = detect_ai_upscaler()
    if not enabled:
        return {"applied": False, "reason": "disabled", **status.to_dict()}
    if not status.available:
        logger.warning("AI upscale requested but unavailable: %s", status.message)
        return {"applied": False, "reason": "unavailable", **status.to_dict()}
    # Integration point: frame-extract → upscaler → restitch would risk multi-encode.
    # Keep disabled in-pipeline until a single-pass or lossless-intermediate path is wired.
    logger.info("AI upscaler present (%s) but in-pipeline hook is opt-in/experimental", status.engine)
    return {
        "applied": False,
        "reason": "engine_detected_not_wired_into_single_pass",
        **status.to_dict(),
        "message": (
            f"{status.engine} is installed. ClipForge keeps a single FFmpeg pass (Lanczos) by default "
            "to avoid multi-encode quality loss. Use the engine externally if needed."
        ),
    }
