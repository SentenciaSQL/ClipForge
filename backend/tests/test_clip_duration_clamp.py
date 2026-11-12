"""Clip windows must never exceed the configured max duration."""

from __future__ import annotations

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.duration_clamp import clamp_clip_window, resolved_clip_duration


def test_clamp_trims_long_window_to_max():
    clamped = clamp_clip_window(10.0, 490.0, min_seconds=12.0, max_seconds=30.0, video_duration=600.0)
    assert clamped is not None
    start, end = clamped
    assert abs((end - start) - 30.0) < 0.01
    assert start == 10.0


def test_snap_hard_clamps_sparse_overshoot():
    segments = [
        {"start": 0.0, "end": 5.0, "text": "one"},
        {"start": 60.0, "end": 200.0, "text": "a very long monologue that used to stretch the clip"},
    ]
    snapped = snap_window(
        segments,
        0.0,
        200.0,
        min_seconds=12.0,
        max_seconds=30.0,
        video_duration=300.0,
        min_words=0,
    )
    assert snapped is not None
    start, end, _text = snapped
    assert end - start <= 30.5


def test_resolved_duration_prefers_span_and_caps():
    assert resolved_clip_duration(start_seconds=0, end_seconds=28, duration_seconds=480, max_seconds=180) == 28
    assert resolved_clip_duration(start_seconds=0, end_seconds=500, duration_seconds=500, max_seconds=180) == 180
