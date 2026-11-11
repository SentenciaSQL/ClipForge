"""Tests for CUDA 12 DLL discovery helpers."""

from __future__ import annotations

from pathlib import Path

from app.core import cuda_runtime


def test_detect_cuda_toolkit_major_from_env(monkeypatch):
    monkeypatch.setenv("CUDA_PATH", r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.5")
    monkeypatch.setenv("CUDA_PATH_V13_5", r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.5")
    assert cuda_runtime.detect_cuda_toolkit_major() == 13


def test_ensure_cuda12_hint_mentions_cuda13(monkeypatch):
    monkeypatch.setattr(cuda_runtime.platform, "system", lambda: "Windows")
    monkeypatch.setattr(cuda_runtime, "discover_cuda12_bin_dirs", lambda: [])
    monkeypatch.setattr(cuda_runtime, "find_cublas64_12", lambda: None)
    monkeypatch.setenv("CUDA_PATH", r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.5")
    info = cuda_runtime.ensure_cuda12_dll_path()
    assert info["toolkit_major"] == 13
    assert info["applied"] is False
    assert "CUDA 12" in str(info["hint"])
    assert "nvidia-cublas-cu12" in str(info["hint"])


def test_find_cublas_from_discovered_dir(tmp_path: Path, monkeypatch):
    bin_dir = tmp_path / "nvidia" / "cublas" / "bin"
    bin_dir.mkdir(parents=True)
    dll = bin_dir / "cublas64_12.dll"
    dll.write_bytes(b"fake")
    monkeypatch.setattr(cuda_runtime, "discover_cuda12_bin_dirs", lambda: [bin_dir])
    monkeypatch.setattr(cuda_runtime.os, "environ", {"PATH": ""})
    assert cuda_runtime.find_cublas64_12() == dll
