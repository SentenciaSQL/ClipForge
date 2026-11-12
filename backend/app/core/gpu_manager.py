"""Coordinate VRAM-heavy model lifetimes across Whisper / Ollama / encode stages."""

from __future__ import annotations

import gc
import threading
from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.core.hardware import detect_hardware
from app.core.logging import get_logger

logger = get_logger(__name__)

GpuHolder = Literal["none", "whisper", "ollama", "ffmpeg", "unknown"]


@dataclass
class GpuStatus:
    holder: str
    cuda_available: bool
    gpu_name: str | None
    gpu_vram_gb: float | None
    whisper_loaded: bool
    whisper_key: str | None
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GpuManager:
    """
    Serialize exclusive GPU ownership and aggressively free Whisper weights
    before handing the card to Ollama or FFmpeg NVENC-heavy work.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._holder: GpuHolder = "none"
        self._notes: list[str] = []

    def status(self) -> GpuStatus:
        from app.ai.transcription.whisper_service import whisper_service

        hardware = detect_hardware()
        with self._lock:
            loaded = whisper_service._model is not None  # noqa: SLF001
            key = None
            if whisper_service._loaded_key:  # noqa: SLF001
                key = "/".join(whisper_service._loaded_key)  # noqa: SLF001
            return GpuStatus(
                holder=self._holder,
                cuda_available=hardware.cuda_available,
                gpu_name=hardware.gpu_name,
                gpu_vram_gb=hardware.gpu_vram_gb,
                whisper_loaded=loaded,
                whisper_key=key,
                notes=list(self._notes[-8:]),
            )

    def acquire(self, holder: GpuHolder, *, timeout: float | None = 3600.0) -> bool:
        from app.orchestrator.job_manager import job_manager

        ok = job_manager.gpu_lock.acquire(timeout=timeout)
        if not ok:
            return False
        with self._lock:
            self._holder = holder
            self._notes.append(f"acquired:{holder}")
            logger.info("GPU acquired by %s", holder)
        return True

    def release(self) -> None:
        from app.orchestrator.job_manager import job_manager

        with self._lock:
            previous = self._holder
            self._holder = "none"
            self._notes.append(f"released:{previous}")
        job_manager.gpu_lock.release()
        logger.info("GPU released (was %s)", previous)

    def unload_whisper(self, *, reason: str = "manual") -> dict[str, Any]:
        from app.ai.transcription.whisper_service import whisper_service

        with self._lock:
            was_loaded = whisper_service._model is not None  # noqa: SLF001
            whisper_service.unload()
            freed = self._collect_memory()
            note = f"unload_whisper:{reason}:was_loaded={was_loaded}"
            self._notes.append(note)
            logger.info("Unloaded Whisper (%s) freed=%s", reason, freed)
            return {"unloaded": True, "was_loaded": was_loaded, **freed}

    def prepare_for_llm(self) -> dict[str, Any]:
        """Free Whisper VRAM before Ollama inference."""
        import time

        result = self.unload_whisper(reason="before_ollama")
        # Give the driver a beat to reclaim pages before Ollama loads weights.
        # Without this, Windows often hits "CUDA illegal memory access" in Ollama.
        time.sleep(1.0)
        result.update(self._collect_memory())
        result["settled"] = True
        return result

    def prepare_for_render(self) -> dict[str, Any]:
        """Free Whisper weights before encode (NVENC + host RAM pressure)."""
        return self.unload_whisper(reason="before_render")

    def _collect_memory(self) -> dict[str, Any]:
        collected = gc.collect()
        cuda_cleared = False
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                cuda_cleared = True
        except Exception as exc:  # noqa: BLE001
            logger.debug("CUDA empty_cache skipped: %s", exc)
        return {"gc_collected": collected, "cuda_cache_cleared": cuda_cleared}


gpu_manager = GpuManager()
