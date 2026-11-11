"""Reframe must tolerate broken/incomplete OpenCV installs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.media import reframe


def test_detect_subject_falls_back_when_cascade_missing(monkeypatch):
    fake_cv2 = SimpleNamespace(
        VideoCapture=object,
        cvtColor=object,
        data=SimpleNamespace(haarcascades=""),
        # CascadeClassifier intentionally missing
    )
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)
    # Force re-import path through _opencv_ready
    ratio = reframe.detect_subject_x_ratio(
        Path("dummy.mp4"),
        start_seconds=0,
        duration_seconds=10,
    )
    assert ratio is None


def test_plan_reframe_uses_center_when_faces_unavailable(monkeypatch):
    monkeypatch.setattr(reframe, "detect_subject_x_ratio", lambda *a, **k: None)
    plan = reframe.plan_reframe_for_clip(
        Path("dummy.mp4"),
        start_seconds=0,
        duration_seconds=15,
        source_width=640,
        source_height=360,
        output_width=1080,
        output_height=1920,
        mode="auto",
    )
    assert plan.mode == "center_crop"
    assert "crop=" in plan.filter_chain
