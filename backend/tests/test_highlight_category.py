"""Regression tests for LLM highlight category coercion."""

from __future__ import annotations

from app.ai.highlights.schemas import HighlightProposal, HighlightProposalBatch, normalize_highlight_category


def test_normalize_unknown_category_to_general():
    assert normalize_highlight_category("request") == "qa"
    assert normalize_highlight_category("totally_made_up") == "general"
    assert normalize_highlight_category(None) == "general"
    assert normalize_highlight_category("HOOK") == "hook"


def test_proposal_accepts_request_category():
    proposal = HighlightProposal.model_validate(
        {
            "start_seconds": 10,
            "end_seconds": 25,
            "hook": "Can you do this?",
            "category": "request",
        }
    )
    assert proposal.category == "qa"


def test_batch_with_invented_category_does_not_raise():
    batch = HighlightProposalBatch.model_validate(
        {
            "candidates": [
                {
                    "start_seconds": 1,
                    "end_seconds": 20,
                    "hook": "Listen to this",
                    "category": "hook",
                },
                {
                    "start_seconds": 30,
                    "end_seconds": 50,
                    "hook": "Please subscribe",
                    "category": "request",
                },
            ]
        }
    )
    assert len(batch.candidates) == 2
    assert batch.candidates[1].category == "qa"
