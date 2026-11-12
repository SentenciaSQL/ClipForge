"""Pydantic contracts for LLM highlight proposals."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

HighlightCategory = Literal[
    "hook",
    "story",
    "advice",
    "educational",
    "controversial",
    "emotional",
    "funny",
    "revelation",
    "qa",
    "conclusion",
    "memorable",
    "general",
]

ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    (
        "hook",
        "story",
        "advice",
        "educational",
        "controversial",
        "emotional",
        "funny",
        "revelation",
        "qa",
        "conclusion",
        "memorable",
        "general",
    )
)

# Common LLM invents / near-synonyms → canonical label.
_CATEGORY_ALIASES: dict[str, HighlightCategory] = {
    "request": "qa",
    "question": "qa",
    "q&a": "qa",
    "q_and_a": "qa",
    "howto": "advice",
    "how-to": "advice",
    "how_to": "advice",
    "tip": "advice",
    "tips": "advice",
    "tutorial": "educational",
    "lesson": "educational",
    "teach": "educational",
    "teaching": "educational",
    "drama": "controversial",
    "debate": "controversial",
    "humor": "funny",
    "joke": "funny",
    "comedy": "funny",
    "sad": "emotional",
    "inspiring": "emotional",
    "inspiration": "emotional",
    "twist": "revelation",
    "surprise": "revelation",
    "ending": "conclusion",
    "outro": "conclusion",
    "intro": "hook",
    "opener": "hook",
    "anecdote": "story",
    "narrative": "story",
    "quote": "memorable",
    "other": "general",
    "misc": "general",
    "unknown": "general",
}


def normalize_highlight_category(value: Any) -> HighlightCategory:
    """Map free-form LLM category strings onto the allowed enum."""
    if value is None:
        return "general"
    raw = str(value).strip().lower().replace(" ", "_")
    if not raw:
        return "general"
    if raw in ALLOWED_CATEGORIES:
        return raw  # type: ignore[return-value]
    if raw in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[raw]
    # Soft prefix / contains match for things like "educational_tip"
    for allowed in ALLOWED_CATEGORIES:
        if allowed in raw or raw in allowed:
            return allowed  # type: ignore[return-value]
    return "general"


class HighlightProposal(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    hook: str = Field(min_length=1)
    category: HighlightCategory = "general"
    description: str = ""
    reason: str = ""
    hook_strength: float = Field(default=50, ge=0, le=100)
    content_value: float = Field(default=50, ge=0, le=100)
    emotional_engagement: float = Field(default=50, ge=0, le=100)
    message_clarity: float = Field(default=50, ge=0, le=100)
    segment_independence: float = Field(default=50, ge=0, le=100)
    ending_quality: float = Field(default=50, ge=0, le=100)

    @field_validator("category", mode="before")
    @classmethod
    def _coerce_category(cls, value: Any) -> HighlightCategory:
        return normalize_highlight_category(value)

    @field_validator("hook", mode="before")
    @classmethod
    def _coerce_hook(cls, value: Any) -> str:
        text = str(value or "").strip()
        return text or "Highlight moment"

    @model_validator(mode="before")
    @classmethod
    def _coerce_timestamps(cls, value: Any) -> Any:
        """Normalize common LLM shape quirks (duration instead of end, aliases)."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "start_seconds" not in data:
            for key in ("start", "begin", "begin_seconds", "from"):
                if key in data:
                    data["start_seconds"] = data[key]
                    break
        if "end_seconds" not in data:
            for key in ("end", "finish", "to", "stop_seconds"):
                if key in data:
                    data["end_seconds"] = data[key]
                    break
        if "end_seconds" not in data:
            start = data.get("start_seconds")
            duration = data.get("duration_seconds", data.get("duration", data.get("length")))
            try:
                if start is not None and duration is not None:
                    data["end_seconds"] = float(start) + float(duration)
            except (TypeError, ValueError):
                pass
        return data

    @field_validator("end_seconds")
    @classmethod
    def _end_after_start(cls, value: float, info: ValidationInfo) -> float:
        start = info.data.get("start_seconds")
        if start is not None and value <= float(start):
            raise ValueError("end_seconds must be greater than start_seconds")
        return value


class HighlightProposalBatch(BaseModel):
    candidates: list[HighlightProposal] = Field(default_factory=list)
