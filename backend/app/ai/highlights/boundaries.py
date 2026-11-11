"""Snap LLM timestamps onto real transcript segment boundaries."""

from __future__ import annotations

from typing import Any


def _segment_text(segments: list[dict[str, Any]], start: float, end: float) -> str:
    parts = [
        str(seg.get("text") or "").strip()
        for seg in segments
        if float(seg.get("end", 0)) > start and float(seg.get("start", 0)) < end
    ]
    return " ".join(p for p in parts if p).strip()


def snap_window(
    segments: list[dict[str, Any]],
    start: float,
    end: float,
    *,
    min_seconds: float = 12.0,
    max_seconds: float = 30.0,
    video_duration: float | None = None,
    min_words: int = 5,
) -> tuple[float, float, str] | None:
    """
    Validate and adjust a proposed window against transcript segments.

    - Prefer complete segment boundaries
    - Expand/shrink into [min_seconds, max_seconds]
    - Reject windows that cannot cover real transcript content

    For sparse dialogue (trailers, ads), expansion may span silence between lines
    so wall-clock duration reaches min_seconds even when speech is short.
    """
    if not segments:
        return None

    ordered = sorted(segments, key=lambda s: float(s.get("start", 0)))
    max_end = video_duration if video_duration is not None else float(ordered[-1].get("end", end))

    # Find nearest segment starts/ends
    start_candidates = [float(s.get("start", 0)) for s in ordered]
    end_candidates = [float(s.get("end", 0)) for s in ordered]

    snapped_start = min(start_candidates, key=lambda value: abs(value - start))
    snapped_end = min(end_candidates, key=lambda value: abs(value - end))

    if snapped_end <= snapped_start:
        # Fall back to covering the nearest segment around the proposed midpoint.
        mid = (start + end) / 2.0
        nearest = min(ordered, key=lambda s: abs(((float(s["start"]) + float(s["end"])) / 2.0) - mid))
        snapped_start = float(nearest["start"])
        snapped_end = float(nearest["end"])

    duration = snapped_end - snapped_start

    # Expand forward/backward using adjacent segments to reach min duration.
    start_idx = next((i for i, s in enumerate(ordered) if abs(float(s["start"]) - snapped_start) < 1e-3), 0)
    end_idx = next(
        (i for i, s in enumerate(ordered) if abs(float(s["end"]) - snapped_end) < 1e-3),
        len(ordered) - 1,
    )

    while duration < min_seconds and (start_idx > 0 or end_idx < len(ordered) - 1):
        can_left = start_idx > 0
        can_right = end_idx < len(ordered) - 1
        # Prefer expanding toward more content; allow exceeding max briefly then shrink.
        if can_right and (not can_left or (float(ordered[end_idx]["end"]) - snapped_start) <= max_seconds + 1.0):
            end_idx += 1
            snapped_end = float(ordered[end_idx]["end"])
        elif can_left:
            start_idx -= 1
            snapped_start = float(ordered[start_idx]["start"])
        else:
            break
        duration = snapped_end - snapped_start

    # If still short, pad with silence up to min_seconds within the video bounds.
    # Trailers often have sparse dialogue lines shorter than 12s even after merging.
    if duration < min_seconds:
        deficit = min_seconds - duration
        pad_left = min(deficit / 2.0, snapped_start)
        pad_right = deficit - pad_left
        snapped_start = max(0.0, snapped_start - pad_left)
        snapped_end = min(max_end, snapped_end + pad_right)
        # If right hit the wall, push remaining pad to the left.
        still_short = min_seconds - (snapped_end - snapped_start)
        if still_short > 0.05:
            snapped_start = max(0.0, snapped_start - still_short)
        duration = snapped_end - snapped_start

    # Shrink from the weaker edge if still too long.
    while duration > max_seconds and end_idx > start_idx:
        left_span = float(ordered[end_idx]["end"]) - float(ordered[start_idx + 1]["start"])
        right_span = float(ordered[end_idx - 1]["end"]) - float(ordered[start_idx]["start"])
        # Prefer keeping the opening hook; trim the end first when both remain valid.
        if right_span >= min_seconds:
            end_idx -= 1
            snapped_end = float(ordered[end_idx]["end"])
        elif left_span >= min_seconds:
            start_idx += 1
            snapped_start = float(ordered[start_idx]["start"])
        else:
            break
        duration = snapped_end - snapped_start

    snapped_start = max(0.0, snapped_start)
    snapped_end = min(max_end, snapped_end)
    duration = snapped_end - snapped_start
    if duration < min_seconds - 0.25 or duration > max_seconds + 0.5:
        return None

    text = _segment_text(ordered, snapped_start, snapped_end)
    words = [w for w in text.split() if w]
    if len(words) < max(1, min_words):
        return None
    return snapped_start, snapped_end, text
