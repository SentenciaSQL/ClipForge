"""Ollama CUDA detection + highlight proposal coercion."""

from __future__ import annotations

from app.ai.highlights.schemas import HighlightProposal
from app.ai.llm.ollama_client import _is_cuda_failure


def test_detects_cuda_illegal_memory_access():
    body = '{"error":"an error was encountered while running the model: CUDA error\\nCUDA error: an illegal memory access was encountered"}'
    assert _is_cuda_failure(500, body)


def test_ignores_non_cuda_client_errors():
    assert not _is_cuda_failure(400, '{"error":"bad request"}')
    assert not _is_cuda_failure(500, '{"error":"model not found"}')


def test_proposal_accepts_duration_instead_of_end():
    item = HighlightProposal.model_validate(
        {
            "start_seconds": 340.25,
            "duration_seconds": 18.0,
            "hook": "Big reveal",
            "category": "revelation",
            "ending_quality": 70,
        }
    )
    assert item.end_seconds == 358.25
    assert item.hook == "Big reveal"


def test_proposal_accepts_start_end_aliases():
    item = HighlightProposal.model_validate(
        {
            "start": 10,
            "end": 25,
            "hook": "",
            "category": "howto",
        }
    )
    assert item.start_seconds == 10
    assert item.end_seconds == 25
    assert item.hook == "Highlight moment"
    assert item.category == "advice"


def test_proposal_accepts_missing_hook_and_score_aliases():
    item = HighlightProposal.model_validate(
        {
            "start_seconds": 288.94,
            "end_seconds": 305.0,
            "category": "story",
            "engagement": 90,
            "clarity": 85,
        }
    )
    assert item.hook.startswith("Moment 289")
    assert item.emotional_engagement == 90
    assert item.message_clarity == 85


def test_proposal_uses_title_when_hook_missing():
    item = HighlightProposal.model_validate(
        {
            "start_seconds": 10,
            "end_seconds": 25,
            "title": "You won't believe this",
        }
    )
    assert item.hook == "You won't believe this"
