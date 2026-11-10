"""Weighted engagement-potential scoring for clip candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_WEIGHTS: dict[str, float] = {
    "hook_strength": 0.25,
    "content_value": 0.20,
    "emotional_engagement": 0.15,
    "message_clarity": 0.15,
    "segment_independence": 0.10,
    "audio_quality": 0.10,
    "ending_quality": 0.05,
}


@dataclass
class ScoreResult:
    score: float
    breakdown: dict[str, float]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def estimate_audio_quality(segment: dict[str, Any] | None = None) -> float:
    """
    Lightweight heuristic from Whisper segment stats when available.
    Not a true loudness meter — refined in later audio phases.
    """
    if not segment:
        return 70.0
    no_speech = segment.get("no_speech_prob")
    avg_logprob = segment.get("avg_logprob")
    score = 70.0
    if isinstance(no_speech, (int, float)):
        score -= clamp(float(no_speech) * 100.0, 0, 40)
    if isinstance(avg_logprob, (int, float)):
        # avg_logprob closer to 0 is better
        score += clamp((float(avg_logprob) + 1.0) * 20.0, -20, 20)
    return clamp(score)


def score_candidate(
    metrics: dict[str, float],
    *,
    weights: dict[str, float] | None = None,
    audio_quality: float = 70.0,
) -> ScoreResult:
    merged = {
        "hook_strength": clamp(float(metrics.get("hook_strength", 50))),
        "content_value": clamp(float(metrics.get("content_value", 50))),
        "emotional_engagement": clamp(float(metrics.get("emotional_engagement", 50))),
        "message_clarity": clamp(float(metrics.get("message_clarity", 50))),
        "segment_independence": clamp(float(metrics.get("segment_independence", 50))),
        "audio_quality": clamp(audio_quality),
        "ending_quality": clamp(float(metrics.get("ending_quality", 50))),
    }
    active_weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(active_weights.values()) or 1.0
    score = 0.0
    for key, weight in active_weights.items():
        score += merged.get(key, 50.0) * (weight / total_weight)
    return ScoreResult(score=round(clamp(score), 2), breakdown={k: round(v, 2) for k, v in merged.items()})
