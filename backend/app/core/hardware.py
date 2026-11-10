"""Detect local hardware capabilities and adapt processing strategy."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class HardwareProfile:
    os_name: str
    python_version: str
    cpu_count: int
    ram_gb: float | None
    ffmpeg_available: bool
    ffmpeg_path: str | None
    ffprobe_available: bool
    ffprobe_path: str | None
    ffmpeg_has_libass: bool
    ffmpeg_has_nvenc: bool
    cuda_available: bool
    gpu_name: str | None
    gpu_vram_gb: float | None
    ollama_available: bool
    ollama_url: str
    ollama_models: list[str] = field(default_factory=list)
    recommended_device: str = "cpu"
    max_concurrent_jobs: int = 1
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _resolve_binary(configured: str, fallback_names: list[str]) -> str | None:
    if configured:
        path = shutil.which(configured) or (configured if PathExists(configured) else None)
        return path
    for name in fallback_names:
        found = shutil.which(name)
        if found:
            return found
    return None


def PathExists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()


def _probe_ffmpeg_features(ffmpeg_path: str | None) -> tuple[bool, bool]:
    if not ffmpeg_path:
        return False, False
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        has_nvenc = "h264_nvenc" in output or "hevc_nvenc" in output
        filters = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        filter_out = (filters.stdout or "") + (filters.stderr or "")
        has_libass = "subtitles" in filter_out or "ass" in filter_out
        return has_libass, has_nvenc
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Failed to probe FFmpeg features: %s", exc)
        return False, False


def _detect_ram_gb() -> float | None:
    try:
        import psutil  # type: ignore

        return round(psutil.virtual_memory().total / (1024**3), 1)
    except Exception:
        pass
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024**2), 1)
    except OSError:
        return None
    return None


def _detect_nvidia() -> tuple[bool, str | None, float | None]:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False, None, None
    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False, None, None
        first = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in first.split(",")]
        name = parts[0] if parts else None
        vram = None
        if len(parts) > 1:
            try:
                vram = round(float(parts[1]) / 1024, 1)
            except ValueError:
                vram = None
        return True, name, vram
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("nvidia-smi probe failed: %s", exc)
        return False, None, None


def _detect_ollama(settings: Settings) -> tuple[bool, list[str]]:
    try:
        import urllib.request

        url = f"{settings.ollama_url.rstrip('/')}/api/tags"
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
        models = [item.get("name", "") for item in payload.get("models", []) if item.get("name")]
        return True, models
    except Exception:
        return False, []


@lru_cache
def detect_hardware() -> HardwareProfile:
    settings = get_settings()
    ffmpeg_path = _resolve_binary(settings.ffmpeg_path, ["ffmpeg", "ffmpeg.exe"])
    ffprobe_path = _resolve_binary(settings.ffprobe_path, ["ffprobe", "ffprobe.exe"])
    has_libass, has_nvenc = _probe_ffmpeg_features(ffmpeg_path)
    cuda_available, gpu_name, gpu_vram = _detect_nvidia()
    ollama_available, ollama_models = _detect_ollama(settings)

    notes: list[str] = []
    recommended = "cpu"
    if settings.prefer_gpu and cuda_available:
        recommended = "cuda"
    else:
        if settings.prefer_gpu and not cuda_available:
            notes.append("GPU preferred but CUDA/nvidia-smi not available; using CPU fallback.")
        recommended = "cpu"

    if not ffmpeg_path:
        notes.append("FFmpeg not found. Install FFmpeg and ensure it is on PATH.")
    if not ffprobe_path:
        notes.append("FFprobe not found. Install FFmpeg (includes ffprobe).")
    if not ollama_available:
        notes.append("Ollama is not reachable. Semantic analysis requires a local Ollama server.")
    elif settings.ollama_model not in ollama_models and not any(
        m.startswith(settings.ollama_model.split(":")[0]) for m in ollama_models
    ):
        notes.append(
            f"Configured Ollama model '{settings.ollama_model}' not found. "
            f"Available: {', '.join(ollama_models) or 'none'}."
        )

    import os

    profile = HardwareProfile(
        os_name=f"{platform.system()} {platform.release()}",
        python_version=platform.python_version(),
        cpu_count=os.cpu_count() or 1,
        ram_gb=_detect_ram_gb(),
        ffmpeg_available=bool(ffmpeg_path),
        ffmpeg_path=ffmpeg_path,
        ffprobe_available=bool(ffprobe_path),
        ffprobe_path=ffprobe_path,
        ffmpeg_has_libass=has_libass,
        ffmpeg_has_nvenc=has_nvenc and cuda_available,
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram,
        ollama_available=ollama_available,
        ollama_url=settings.ollama_url,
        ollama_models=ollama_models,
        recommended_device=recommended,
        max_concurrent_jobs=max(1, settings.max_concurrent_jobs),
        notes=notes,
    )
    logger.info(
        "Hardware profile: device=%s ffmpeg=%s cuda=%s ollama=%s",
        profile.recommended_device,
        profile.ffmpeg_available,
        profile.cuda_available,
        profile.ollama_available,
    )
    return profile


def refresh_hardware_profile() -> HardwareProfile:
    detect_hardware.cache_clear()
    return detect_hardware()
