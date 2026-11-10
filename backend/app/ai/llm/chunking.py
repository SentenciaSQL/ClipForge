"""Overlapping transcript windows for local LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TranscriptChunk:
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    segments: list[dict[str, Any]]


def chunk_segments(
    segments: list[dict[str, Any]],
    *,
    window_seconds: float = 90.0,
    overlap_seconds: float = 20.0,
    min_window_seconds: float = 20.0,
) -> list[TranscriptChunk]:
    """
    Build overlapping windows from timestamped transcript segments.

    Windows preserve conversational context without sending the entire transcript
    in one LLM request.
    """
    if not segments:
        return []

    normalized: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        normalized.append(
            {
                "id": seg.get("id"),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": text,
            }
        )
    if not normalized:
        return []

    total_end = max(item["end"] for item in normalized)
    if total_end <= window_seconds:
        text = " ".join(item["text"] for item in normalized)
        return [
            TranscriptChunk(
                index=0,
                start_seconds=normalized[0]["start"],
                end_seconds=normalized[-1]["end"],
                text=text,
                segments=normalized,
            )
        ]

    step = max(window_seconds - overlap_seconds, min_window_seconds)
    chunks: list[TranscriptChunk] = []
    cursor = normalized[0]["start"]
    index = 0

    while cursor < total_end:
        window_end = cursor + window_seconds
        selected = [item for item in normalized if item["end"] > cursor and item["start"] < window_end]
        if not selected:
            cursor += step
            continue
        text = " ".join(item["text"] for item in selected)
        chunks.append(
            TranscriptChunk(
                index=index,
                start_seconds=selected[0]["start"],
                end_seconds=selected[-1]["end"],
                text=text,
                segments=selected,
            )
        )
        index += 1
        next_cursor = cursor + step
        if selected[-1]["end"] >= total_end - 0.5:
            break
        cursor = next_cursor

    return chunks
