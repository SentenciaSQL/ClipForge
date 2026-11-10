"""Pydantic contracts for LLM highlight proposals."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

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

    @field_validator("end_seconds")
    @classmethod
    def _end_after_start(cls, value: float, info: ValidationInfo) -> float:
        start = info.data.get("start_seconds")
        if start is not None and value <= float(start):
            raise ValueError("end_seconds must be greater than start_seconds")
        return value


class HighlightProposalBatch(BaseModel):
    candidates: list[HighlightProposal] = Field(default_factory=list)
