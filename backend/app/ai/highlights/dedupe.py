"""Overlap handling and distinct clip selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RankedCandidate:
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    transcript: str
    hook: str
    category: str
    description: str
    reason: str
    score: float
    score_breakdown: dict[str, float]
    source_chunk: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_seconds": self.start_seconds,
            "end_seconds": self.end_seconds,
            "duration_seconds": self.duration_seconds,
            "transcript": self.transcript,
            "hook": self.hook,
            "category": self.category,
            "description": self.description,
            "reason": self.reason,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "source_chunk": self.source_chunk,
        }


def overlap_ratio(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    if overlap <= 0:
        return 0.0
    shorter = max(min(a_end - a_start, b_end - b_start), 1e-6)
    return overlap / shorter


def select_distinct_candidates(
    candidates: list[RankedCandidate],
    *,
    max_count: int = 5,
    max_overlap: float = 0.45,
) -> list[RankedCandidate]:
    """Greedy select highest-score clips that are sufficiently distinct."""
    ordered = sorted(candidates, key=lambda item: item.score, reverse=True)
    selected: list[RankedCandidate] = []
    for candidate in ordered:
        if any(
            overlap_ratio(
                candidate.start_seconds,
                candidate.end_seconds,
                other.start_seconds,
                other.end_seconds,
            )
            > max_overlap
            for other in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= max_count:
            break
    return selected
