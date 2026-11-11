"""Regression: clips must work without mandatory spoken words."""

from __future__ import annotations

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.heuristic import build_duration_windows, build_heuristic_candidates


def _sparse_trailer_segments() -> list[dict]:
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
        min_words=0,
    )
    assert snapped is not None
    start, end, text = snapped
    assert end - start >= 11.75
    assert "What you doing" in text


def test_snap_allows_empty_transcript_with_duration_only():
    snapped = snap_window(
        [],
        10.0,
        20.0,
        min_seconds=12.0,
        max_seconds=30.0,
        video_duration=90.0,
        min_words=0,
    )
    assert snapped is not None
    start, end, text = snapped
    assert text == ""
    assert end - start >= 11.75


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


def test_duration_windows_for_music_without_speech():
    selected = build_duration_windows(
        video_duration=166.79,
        clip_count=4,
        min_seconds=12.0,
        max_seconds=30.0,
    )
    assert len(selected) >= 1
    assert all(c.transcript == "" for c in selected)
    assert all(c.hook for c in selected)
    assert all(12.0 - 0.3 <= c.duration_seconds <= 30.5 for c in selected)


def test_heuristic_falls_back_to_duration_when_no_segments():
    selected = build_heuristic_candidates(
        [],
        clip_count=3,
        min_seconds=12.0,
        max_seconds=30.0,
        video_duration=120.0,
    )
    assert len(selected) >= 1
    assert all(c.transcript == "" for c in selected)
