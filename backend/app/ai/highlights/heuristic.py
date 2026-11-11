"""Highlight fallbacks when the LLM returns no usable clips.

Speech/transcript is optional. Music, rhythm, lyrics-as-atmosphere, and
visual-only moments can still become 12–30s clip windows. Users may replace
or add audio later in an external app.
"""

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


def _format_timecode(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


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
    if hook:
        if len(hook) > 120:
            return hook[:117].rstrip() + "..."
        return hook
    return f"Moment {_format_timecode(start)}–{_format_timecode(end)}"


def _heuristic_score(text: str, *, has_speech: bool) -> dict[str, float]:
    words = _word_count(text)
    if not has_speech or words == 0:
        # Music / visual / rhythm window — still a valid short-form clip.
        return {
            "hook_strength": 55.0,
            "content_value": 50.0,
            "emotional_engagement": 60.0,
            "message_clarity": 45.0,
            "segment_independence": 70.0,
            "ending_quality": 55.0,
        }
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


def build_duration_windows(
    *,
    video_duration: float,
    clip_count: int = 5,
    min_seconds: float = 12.0,
    max_seconds: float = 30.0,
) -> list[RankedCandidate]:
    """
    Slice the timeline into clip-sized windows with no transcript requirement.

    Used for music beds, rhythm edits, and videos where speech is absent or
    will be replaced externally.
    """
    if video_duration <= 0:
        return []

    target = min(max_seconds, max(min_seconds, min(max_seconds, video_duration)))
    if video_duration < min_seconds - 0.25:
        # Whole video as one short clip when shorter than the preferred minimum.
        start, end = 0.0, float(video_duration)
        hook = f"Full clip {_format_timecode(start)}–{_format_timecode(end)}"
        scored = score_candidate(_heuristic_score("", has_speech=False), audio_quality=70.0)
        return [
            RankedCandidate(
                start_seconds=0.0,
                end_seconds=round(end, 3),
                duration_seconds=round(end, 3),
                transcript="",
                hook=hook,
                category="general",
                description="Duration window (video shorter than preferred clip length)",
                reason="No speech required — using the full video as one clip",
                score=scored.score,
                score_breakdown=scored.breakdown,
                source_chunk=0,
            )
        ]

    # Spread windows across the video with mild overlap allowed later by dedupe.
    usable = max(video_duration - target, 0.0)
    count = max(1, clip_count)
    if usable <= 0.5:
        starts = [0.0]
    else:
        step = usable / max(count - 1, 1)
        starts = [i * step for i in range(count)]

    raw: list[RankedCandidate] = []
    for index, start in enumerate(starts):
        end = min(video_duration, start + target)
        if end - start < min_seconds - 0.25 and video_duration >= min_seconds:
            end = min(video_duration, start + min_seconds)
            start = max(0.0, end - min_seconds)
        duration = end - start
        if duration < 1.0:
            continue
        hook = f"Moment {_format_timecode(start)}–{_format_timecode(end)}"
        # Slight preference for earlier hooks (common for trailers/music drops).
        metrics = _heuristic_score("", has_speech=False)
        metrics["hook_strength"] = min(90.0, metrics["hook_strength"] + max(0, 8 - index) * 1.5)
        scored = score_candidate(metrics, audio_quality=70.0)
        raw.append(
            RankedCandidate(
                start_seconds=round(start, 3),
                end_seconds=round(end, 3),
                duration_seconds=round(duration, 3),
                transcript="",
                hook=hook,
                category="general",
                description="Duration/music window without requiring dialogue",
                reason="Speech optional — selected by timeline coverage for music/visual pacing",
                score=scored.score,
                score_breakdown=scored.breakdown,
                source_chunk=index,
            )
        )
    return select_distinct_candidates(raw, max_count=count, max_overlap=0.35)


def build_heuristic_candidates(
    segments: list[dict[str, Any]],
    *,
    clip_count: int = 5,
    min_seconds: float = 12.0,
    max_seconds: float = 30.0,
    video_duration: float | None = None,
) -> list[RankedCandidate]:
    """
    Build clip windows from transcript anchors when available; otherwise from duration.

    Words are never mandatory. Empty/sparse speech still yields music/visual clips.
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
        or seg.get("start") is not None
    ]
    # Keep only real timed rows; blank text is fine.
    ordered = [
        seg
        for seg in ordered
        if float(seg["end"]) > float(seg["start"])
    ]

    raw: list[RankedCandidate] = []
    if ordered:
        last_end = float(ordered[-1]["end"])
        for index, seed in enumerate(ordered):
            seed_start = float(seed["start"])
            seed_end = min(float(seed["end"]) + max_seconds * 0.5, last_end)
            snapped = snap_window(
                ordered,
                seed_start,
                seed_end,
                min_seconds=min_seconds,
                max_seconds=max_seconds,
                video_duration=video_duration,
                min_words=0,
            )
            if not snapped:
                continue
            start, end, text = snapped
            stats = {
                "no_speech_prob": seed.get("no_speech_prob"),
                "avg_logprob": seed.get("avg_logprob"),
            }
            has_speech = _word_count(text) > 0
            metrics = _heuristic_score(text, has_speech=has_speech)
            scored = score_candidate(metrics, audio_quality=estimate_audio_quality(stats))
            raw.append(
                RankedCandidate(
                    start_seconds=round(start, 3),
                    end_seconds=round(end, 3),
                    duration_seconds=round(end - start, 3),
                    transcript=text,
                    hook=_segment_hook(ordered, start, end),
                    category="memorable" if has_speech else "general",
                    description=(
                        "Heuristic fallback from transcript anchors"
                        if has_speech
                        else "Heuristic fallback for music/visual pacing"
                    ),
                    reason=(
                        "Ollama returned no valid clips; selected a speech-anchored window"
                        if has_speech
                        else "Ollama returned no valid clips; selected a non-speech timeline window"
                    ),
                    score=scored.score,
                    score_breakdown=scored.breakdown,
                    source_chunk=index,
                )
            )

    selected = select_distinct_candidates(raw, max_count=max(1, clip_count), max_overlap=0.4)
    if selected:
        return selected

    if video_duration and video_duration > 0:
        return build_duration_windows(
            video_duration=float(video_duration),
            clip_count=clip_count,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
        )
    return []
