"""Loudness normalization helpers for FFmpeg filter graphs."""

from __future__ import annotations


def loudnorm_filter(
    integrated_lufs: float = -14.0,
    true_peak: float = -1.5,
    lra: float = 11.0,
) -> str:
    """
    Return an FFmpeg loudnorm filter string (EBU R128 style).

    Used during final mix/export. Two-pass measurement can be added later
    for higher accuracy; single-pass is sufficient for local short-form exports.
    """
    return (
        f"loudnorm=I={integrated_lufs}:TP={true_peak}:LRA={lra}"
        ":print_format=summary"
    )


def alimiter_filter(limit: float = 0.95) -> str:
    """Simple peak limiter to help prevent clipping after mixing."""
    return f"alimiter=limit={limit}:level=disabled"
