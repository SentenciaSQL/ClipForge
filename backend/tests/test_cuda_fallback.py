"""Unit tests for CUDA runtime error detection and hardware helpers."""

from __future__ import annotations

from app.ai.transcription.whisper_service import _is_cuda_runtime_error
from app.core import hardware


def test_is_cuda_runtime_error_detects_missing_cublas():
    exc = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
    assert _is_cuda_runtime_error(exc) is True


def test_is_cuda_runtime_error_ignores_unrelated_runtime_errors():
    assert _is_cuda_runtime_error(RuntimeError("out of memory while allocating tensor")) is False
    assert _is_cuda_runtime_error(ValueError("cublas missing")) is False


def test_mark_cuda_unusable_blocks_and_clears_cache(monkeypatch):
    hardware._cuda_runtime_blocked = False
    hardware.detect_hardware.cache_clear()

    called = {"cleared": False}
    original = hardware.detect_hardware.cache_clear

    def _clear():
        called["cleared"] = True
        original()

    monkeypatch.setattr(hardware.detect_hardware, "cache_clear", _clear)
    hardware.mark_cuda_unusable("test reason")
    assert hardware.is_cuda_runtime_blocked() is True
    assert called["cleared"] is True
    # Reset for other tests in the same process.
    hardware._cuda_runtime_blocked = False
    hardware.detect_hardware.cache_clear()
