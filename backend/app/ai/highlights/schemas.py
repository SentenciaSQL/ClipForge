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


_SCORE_ALIASES: dict[str, tuple[str, ...]] = {
    "hook_strength": ("hook_score", "hook_power", "hookiness"),
    "content_value": ("value", "content_score", "usefulness"),
    "emotional_engagement": ("engagement", "emotion", "emotional", "emotional_score"),
    "message_clarity": ("clarity", "clearness", "message_clear"),
    "segment_independence": ("independence", "standalone", "self_contained"),
    "ending_quality": ("ending", "close", "closer", "payoff"),
}


class HighlightProposal(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    # Default so LLM responses that omit hook still validate.
    hook: str = Field(default="Highlight moment", min_length=1)
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
    def _coerce_llm_shape(cls, value: Any) -> Any:
        """Normalize common LLM shape quirks (missing hook/end, score aliases)."""
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

        hook = data.get("hook")
        if hook is None or str(hook).strip() == "":
            for key in (
                "title",
                "headline",
                "hook_text",
                "hook_line",
                "summary",
                "text",
                "quote",
                "description",
                "reason",
            ):
                alt = data.get(key)
                if alt is not None and str(alt).strip():
                    data["hook"] = str(alt).strip()
                    break
            else:
                start = data.get("start_seconds")
                end = data.get("end_seconds")
                try:
                    if start is not None and end is not None:
                        data["hook"] = f"Moment {float(start):.0f}s–{float(end):.0f}s"
                    else:
                        data["hook"] = "Highlight moment"
                except (TypeError, ValueError):
                    data["hook"] = "Highlight moment"

        for canonical, aliases in _SCORE_ALIASES.items():
            if canonical in data and data[canonical] is not None:
                continue
            for alias in aliases:
                if alias in data and data[alias] is not None:
                    data[canonical] = data[alias]
                    break

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
