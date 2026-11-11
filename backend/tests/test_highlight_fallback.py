"""Regression: sparse trailer dialogue should still yield clips."""

from __future__ import annotations

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.heuristic import build_heuristic_candidates


def _sparse_trailer_segments() -> list[dict]:
    # Mimics a cinematic trailer: short lines with gaps, ~167s total.
    return [
        {"id": 0, "start": 9.7, "end": 11.0, "text": "What you doing out there?"},
        {"id": 1, "start": 18.2, "end": 20.1, "text": "You gotta be careful."},
        {"id": 2, "start": 34.0, "end": 36.5, "text": "This city will eat you alive."},
        {"id": 3, "start": 52.0, "end": 54.2, "text": "I never asked for this."},
        {"id": 4, "start": 70.5, "end": 73.0, "text": "Then why are you still here?"},
        {"id": 5, "start": 95.0, "end": 97.8, "text": "Because somebody has to."},
        {"id": 6, "start": 120.0, "end": 123.5, "text": "Leonida looks different at night."},
        {"id": 7, "start": 145.0, "end": 148.0, "text": "We take what we want."},
        {"id": 8, "start": 160.0, "end": 163.0, "text": "Welcome to Vice City."},
    ]


def test_snap_pads_sparse_dialogue_to_min_duration():
    segments = _sparse_trailer_segments()
    snapped = snap_window(
        segments,
        9.7,
        11.0,
        min_seconds=12.0,
        max_seconds=30.0,
        video_duration=166.79,
        min_words=3,
    )
    assert snapped is not None
    start, end, text = snapped
    assert end - start >= 11.75
    assert "What you doing" in text


def test_heuristic_fallback_selects_clips_for_trailer():
    selected = build_heuristic_candidates(
        _sparse_trailer_segments(),
        clip_count=3,
        min_seconds=12.0,
        max_seconds=30.0,
        video_duration=166.79,
    )
    assert len(selected) >= 1
    assert all(12.0 - 0.3 <= c.duration_seconds <= 30.5 for c in selected)
    assert all(c.transcript.strip() for c in selected)
