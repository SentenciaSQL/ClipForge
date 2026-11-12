"""Hard wall-clock duration clamps for clip windows."""

from __future__ import annotations


def clamp_clip_window(
    start: float,
    end: float,
    *,
    min_seconds: float = 12.0,
    max_seconds: float = 30.0,
    video_duration: float | None = None,
) -> tuple[float, float] | None:
    """
    Force a window into [min_seconds, max_seconds] within the video.

    Prefer keeping the start (hook) and trimming the end when too long.
    Returns None only when the video itself is shorter than a usable clip.
    """
    if max_seconds < 1:
        max_seconds = 1.0
    if min_seconds < 0.5:
        min_seconds = 0.5
    if min_seconds > max_seconds:
        min_seconds = max_seconds

    start = max(0.0, float(start))
    end = max(start + 0.05, float(end))
    if video_duration is not None and video_duration > 0:
        end = min(end, float(video_duration))
        if end <= start:
            return None

    duration = end - start
    if duration > max_seconds:
        end = start + max_seconds
        if video_duration is not None and video_duration > 0 and end > video_duration:
            end = float(video_duration)
            start = max(0.0, end - max_seconds)
        duration = end - start

    if duration < min_seconds:
        end = start + min_seconds
        if video_duration is not None and video_duration > 0:
            if end > video_duration:
                end = float(video_duration)
                start = max(0.0, end - min_seconds)
            # Video shorter than preferred minimum — keep full remaining span.
            if end - start < min(min_seconds, float(video_duration)) - 0.25:
                if float(video_duration) < 1.0:
                    return None
                start = 0.0
                end = float(video_duration)

    duration = end - start
    if duration < 0.5:
        return None
    return round(start, 3), round(end, 3)


def resolved_clip_duration(
    *,
    start_seconds: float,
    end_seconds: float,
    duration_seconds: float | None,
    max_seconds: float = 180.0,
) -> float:
    """Prefer end-start, fall back to stored duration, then hard-cap."""
    span = float(end_seconds) - float(start_seconds)
    stored = float(duration_seconds) if duration_seconds is not None else span
    duration = span if span > 0.05 else stored
    if duration <= 0.05:
        duration = max(stored, 1.0)
    return min(max(duration, 0.5), float(max_seconds))
