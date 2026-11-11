"""Transcript-only highlight fallback when the LLM returns no usable clips."""

from __future__ import annotations

import re
from typing import Any

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.dedupe import RankedCandidate, select_distinct_candidates
from app.scoring.viral_score import estimate_audio_quality, score_candidate

_QUESTION_RE = re.compile(r"\?")
_HOOKY_RE = re.compile(
    r"\b(what|why|how|wait|look|listen|never|always|secret|truth|love|hate|kill|dead|money|power)\b",
    re.IGNORECASE,
)


def _word_count(text: str) -> int:
    return len([w for w in text.replace("\n", " ").split(" ") if w.strip()])


def _segment_hook(segments: list[dict[str, Any]], start: float, end: float) -> str:
    parts: list[str] = []
    for seg in segments:
        if float(seg.get("end", 0)) <= start or float(seg.get("start", 0)) >= end:
            continue
        text = str(seg.get("text") or "").strip()
        if text:
            parts.append(text)
        if _word_count(" ".join(parts)) >= 8:
            break
    hook = " ".join(parts).strip()
    if len(hook) > 120:
        hook = hook[:117].rstrip() + "..."
    return hook or "Highlight moment"


def _heuristic_score(text: str) -> dict[str, float]:
    words = _word_count(text)
    questions = len(_QUESTION_RE.findall(text))
    hooky = len(_HOOKY_RE.findall(text))
    hook_strength = min(95.0, 40.0 + questions * 15.0 + hooky * 5.0 + min(words, 40) * 0.5)
    content_value = min(90.0, 35.0 + min(words, 60) * 0.8)
    emotional = min(90.0, 40.0 + hooky * 6.0)
    clarity = min(90.0, 45.0 + min(words, 50) * 0.6)
    independence = 70.0 if words >= 12 else 55.0
    ending = 60.0 + (10.0 if text.rstrip().endswith((".", "!", "?")) else 0.0)
    return {
        "hook_strength": hook_strength,
        "content_value": content_value,
        "emotional_engagement": emotional,
        "message_clarity": clarity,
        "segment_independence": independence,
        "ending_quality": ending,
    }


def build_heuristic_candidates(
    segments: list[dict[str, Any]],
    *,
    clip_count: int = 5,
    min_seconds: float = 12.0,
    max_seconds: float = 30.0,
    video_duration: float | None = None,
) -> list[RankedCandidate]:
    """
    Build clip windows by walking transcript segments when Ollama finds nothing.

    Useful for trailers / sparse dialogue where the LLM returns an empty list
    even though usable 12–30s speech windows exist.
    """
    ordered = [
        {
            "id": seg.get("id"),
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", 0.0)),
            "text": str(seg.get("text") or "").strip(),
            "no_speech_prob": seg.get("no_speech_prob"),
            "avg_logprob": seg.get("avg_logprob"),
        }
        for seg in segments
        if str(seg.get("text") or "").strip()
    ]
    if not ordered:
        return []

    raw: list[RankedCandidate] = []
    # Seed a window at each segment start; snap_window expands/shrinks to range.
    for index, seed in enumerate(ordered):
        seed_start = float(seed["start"])
        seed_end = min(float(seed["end"]) + max_seconds * 0.5, float(ordered[-1]["end"]))
        snapped = snap_window(
            ordered,
            seed_start,
            seed_end,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            video_duration=video_duration,
            min_words=5,
        )
        if not snapped:
            continue
        start, end, text = snapped
        if _word_count(text) < 5:
            continue
        stats = {
            "no_speech_prob": seed.get("no_speech_prob"),
            "avg_logprob": seed.get("avg_logprob"),
        }
        metrics = _heuristic_score(text)
        scored = score_candidate(metrics, audio_quality=estimate_audio_quality(stats))
        raw.append(
            RankedCandidate(
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                duration_seconds=round(end - start, 3),
                transcript=text,
                hook=_segment_hook(ordered, start, end),
                category="memorable",
                description="Heuristic fallback from transcript density",
                reason="Ollama returned no valid clips; selected a dense speech window",
                score=scored.score,
                score_breakdown=scored.breakdown,
                source_chunk=index,
            )
        )

    return select_distinct_candidates(raw, max_count=max(1, clip_count), max_overlap=0.4)
