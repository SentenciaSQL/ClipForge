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
