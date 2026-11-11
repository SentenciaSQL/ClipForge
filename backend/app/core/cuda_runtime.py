"""Ensure CUDA 12 runtime DLLs are visible to CTranslate2 on Windows.

Faster-Whisper / CTranslate2 wheels are built for CUDA 12 and load
``cublas64_12.dll``. Installing CUDA Toolkit 13.x alone is not enough —
those installs ship ``cublas64_13.dll``, which is not ABI-compatible.

Preferred light fix: ``pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
nvidia-cuda-nvrtc-cu12`` and let this module prepend their ``bin`` folders
to ``PATH`` (and ``os.add_dll_directory``) before Whisper loads.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_CUBLAS12 = "cublas64_12.dll"
_applied = False
_missing_logged = False


def _unique_dirs(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def discover_cuda12_bin_dirs() -> list[Path]:
    """Locate directories that may contain CUDA 12 cuBLAS / cuDNN / NVRTC DLLs."""
    dirs: list[Path] = []

    # 1) NVIDIA pip wheels under site-packages/nvidia/*/bin
    for entry in sys.path:
        nvidia_root = Path(entry) / "nvidia"
        if not nvidia_root.is_dir():
            continue
        for pkg in ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime", "cufft", "curand"):
            candidate = nvidia_root / pkg / "bin"
            if candidate.is_dir():
                dirs.append(candidate)

    # 2) Explicit CUDA 12 toolkit installs (coexist with CUDA 13)
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    toolkit_root = Path(program_files) / "NVIDIA GPU Computing Toolkit" / "CUDA"
    if toolkit_root.is_dir():
        for child in sorted(toolkit_root.iterdir(), reverse=True):
            name = child.name.lower()
            if name.startswith("v12") and (child / "bin").is_dir():
                dirs.append(child / "bin")

    # 3) CUDA_PATH / CUDA_HOME only if they look like 12.x
    for env_name in ("CUDA_PATH", "CUDA_HOME", "CUDA_PATH_V12_6", "CUDA_PATH_V12_4", "CUDA_PATH_V12_1"):
        raw = os.environ.get(env_name)
        if not raw:
            continue
        bin_dir = Path(raw) / "bin"
        if "v12" in Path(raw).name.lower() and bin_dir.is_dir():
            dirs.append(bin_dir)

    return _unique_dirs(dirs)


def find_cublas64_12() -> Path | None:
    for directory in discover_cuda12_bin_dirs():
        candidate = directory / _CUBLAS12
        if candidate.exists():
            return candidate
    # Also scan PATH
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / _CUBLAS12
        if candidate.exists():
            return candidate
    return None


def detect_cuda_toolkit_major() -> int | None:
    """Best-effort major version from CUDA_PATH* env vars."""
    import re

    for key, value in os.environ.items():
        if not (key == "CUDA_PATH" or key.startswith("CUDA_PATH_V") or key == "CUDA_HOME"):
            continue
        if not value:
            continue
        # Handle Windows paths even when running tests on Linux.
        leaf = value.replace("\\", "/").rstrip("/").split("/")[-1].lower()
        match = re.search(r"v?(\d+)(?:\.\d+)?$", leaf)
        if match:
            return int(match.group(1))
        match = re.search(r"V(\d+)", key)
        if match:
            return int(match.group(1))
    return None


def ensure_cuda12_dll_path() -> dict[str, object]:
    """
    Prepend CUDA 12 DLL directories to PATH on Windows so CTranslate2 can LoadLibrary them.

    Safe to call multiple times; no-op on non-Windows.
    """
    global _applied
    result: dict[str, object] = {
        "platform": platform.system(),
        "applied": False,
        "cublas64_12": None,
        "prepended": [],
        "toolkit_major": detect_cuda_toolkit_major(),
        "hint": None,
    }
    if platform.system() != "Windows":
        return result

    bins = discover_cuda12_bin_dirs()
    prepended: list[str] = []
    path_parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    for directory in bins:
        text = str(directory)
        if text not in path_parts:
            path_parts.insert(0, text)
            prepended.append(text)
        try:
            os.add_dll_directory(text)  # type: ignore[attr-defined]
        except (OSError, AttributeError):
            pass

    if prepended or bins:
        os.environ["PATH"] = os.pathsep.join(path_parts)

    cublas = find_cublas64_12()
    result["cublas64_12"] = str(cublas) if cublas else None
    result["prepended"] = prepended
    result["applied"] = bool(cublas)
    _applied = bool(cublas)

    toolkit_major = result["toolkit_major"]
    if not cublas:
        if isinstance(toolkit_major, int) and toolkit_major >= 13:
            result["hint"] = (
                f"CUDA Toolkit {toolkit_major} is installed, but Faster-Whisper needs "
                "cublas64_12.dll (CUDA 12). Install CUDA Toolkit 12.x alongside, or run: "
                "pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12"
            )
        else:
            result["hint"] = (
                "cublas64_12.dll not found. Install CUDA Toolkit 12.x, or: "
                "pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12"
            )
        global _missing_logged
        if not _missing_logged:
            logger.warning("%s", result["hint"])
            _missing_logged = True
    elif prepended:
        logger.info("CUDA 12 DLL path ready: %s (prepended %s dirs)", cublas, len(prepended))
    else:
        logger.info("CUDA 12 DLL available: %s", cublas)

    return result


def cuda12_runtime_ready() -> bool:
    if platform.system() != "Windows":
        return True
    if not _applied:
        ensure_cuda12_dll_path()
    return find_cublas64_12() is not None
