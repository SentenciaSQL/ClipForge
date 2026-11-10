"""Semantic highlight detection via local Ollama models."""

from __future__ import annotations

from typing import Any

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.dedupe import RankedCandidate, select_distinct_candidates
from app.ai.highlights.schemas import HighlightProposal, HighlightProposalBatch
from app.ai.llm.chunking import TranscriptChunk, chunk_segments
from app.ai.llm.ollama_client import OllamaClient, OllamaError, ollama_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.scoring.viral_score import estimate_audio_quality, score_candidate

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an expert short-form video editor for TikTok, Reels, and Shorts.
Analyze transcript windows and propose clip candidates that work as standalone vertical videos.

Rules:
- Return ONLY valid JSON matching the schema.
- Propose moments with strong hooks that make sense independently.
- Avoid starting mid-sentence or ending before an idea completes.
- Prefer complete ideas: stories, advice, educational explanations, controversy, emotion, humor, revelations, Q&A, conclusions, memorable statements.
- Candidate duration should target 12 to 30 seconds.
- Use timestamps that refer to the absolute times provided in the transcript window.
- Scores are 0-100 estimates of engagement potential, not guaranteed virality.
"""


def _user_prompt(chunk: TranscriptChunk, min_seconds: int, max_seconds: int) -> str:
    lines = [
        f"Window {chunk.index}: {chunk.start_seconds:.2f}s → {chunk.end_seconds:.2f}s",
        f"Target clip duration: {min_seconds}-{max_seconds} seconds.",
        "Transcript segments:",
    ]
    for seg in chunk.segments:
        lines.append(f"[{seg['start']:.2f}-{seg['end']:.2f}] {seg['text']}")
    lines.append(
        "Respond with JSON object:"
        '{"candidates":[{"start_seconds":0,"end_seconds":0,"hook":"",'
        '"category":"hook|story|advice|educational|controversial|emotional|funny|revelation|qa|conclusion|memorable|general",'
        '"description":"","reason":"","hook_strength":0,"content_value":0,'
        '"emotional_engagement":0,"message_clarity":0,"segment_independence":0,"ending_quality":0}]}'
    )
    lines.append("Return 0-5 candidates for this window. Empty candidates array is allowed.")
    return "\n".join(lines)


def _covering_segment_stats(segments: list[dict[str, Any]], start: float, end: float) -> dict[str, Any] | None:
    covering = [
        seg
        for seg in segments
        if float(seg.get("end", 0)) > start and float(seg.get("start", 0)) < end
    ]
    if not covering:
        return None
    # Average available stats
    no_speech_vals = [float(s["no_speech_prob"]) for s in covering if s.get("no_speech_prob") is not None]
    logprob_vals = [float(s["avg_logprob"]) for s in covering if s.get("avg_logprob") is not None]
    return {
        "no_speech_prob": sum(no_speech_vals) / len(no_speech_vals) if no_speech_vals else None,
        "avg_logprob": sum(logprob_vals) / len(logprob_vals) if logprob_vals else None,
    }


class HighlightAnalyzer:
    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client or ollama_client

    def analyze_transcription(
        self,
        segments: list[dict[str, Any]],
        *,
        model: str | None = None,
        clip_count: int = 5,
        min_seconds: int = 12,
        max_seconds: int = 30,
        video_duration: float | None = None,
    ) -> list[RankedCandidate]:
        settings = get_settings()
        model_name = model or settings.ollama_model
        if not self.client.is_available():
            raise OllamaError(
                f"Ollama is not reachable at {self.client.base_url}. Start Ollama and pull {model_name}."
            )

        chunks = chunk_segments(segments, window_seconds=90.0, overlap_seconds=20.0)
        if not chunks:
            return []

        effective_min = min_seconds
        effective_max = max_seconds
        if video_duration is not None and video_duration < min_seconds:
            logger.warning(
                "Video duration %.1fs is shorter than minimum clip length %ss; no 12–30s clips possible",
                video_duration,
                min_seconds,
            )
            return []
        if video_duration is not None:
            effective_max = min(max_seconds, max(int(video_duration), min_seconds))

        raw_candidates: list[RankedCandidate] = []
        for chunk in chunks:
            proposals = self._analyze_chunk(
                chunk,
                model=model_name,
                min_seconds=effective_min,
                max_seconds=effective_max,
            )
            for proposal in proposals:
                snapped = snap_window(
                    segments,
                    proposal.start_seconds,
                    proposal.end_seconds,
                    min_seconds=float(effective_min),
                    max_seconds=float(effective_max),
                    video_duration=video_duration,
                )
                if not snapped:
                    logger.debug(
                        "Rejected proposal outside transcript bounds: %.2f-%.2f",
                        proposal.start_seconds,
                        proposal.end_seconds,
                    )
                    continue
                start, end, text = snapped
                stats = _covering_segment_stats(segments, start, end)
                scored = score_candidate(
                    {
                        "hook_strength": proposal.hook_strength,
                        "content_value": proposal.content_value,
                        "emotional_engagement": proposal.emotional_engagement,
                        "message_clarity": proposal.message_clarity,
                        "segment_independence": proposal.segment_independence,
                        "ending_quality": proposal.ending_quality,
                    },
                    audio_quality=estimate_audio_quality(stats),
                )
                raw_candidates.append(
                    RankedCandidate(
                        start_seconds=round(start, 3),
                        end_seconds=round(end, 3),
                        duration_seconds=round(end - start, 3),
                        transcript=text,
                        hook=proposal.hook.strip(),
                        category=proposal.category,
                        description=proposal.description.strip(),
                        reason=proposal.reason.strip(),
                        score=scored.score,
                        score_breakdown=scored.breakdown,
                        source_chunk=chunk.index,
                    )
                )

        selected = select_distinct_candidates(raw_candidates, max_count=max(1, clip_count))
        logger.info(
            "Highlight analysis produced %s raw / %s selected candidates using %s",
            len(raw_candidates),
            len(selected),
            model_name,
        )
        return selected

    def _analyze_chunk(
        self,
        chunk: TranscriptChunk,
        *,
        model: str,
        min_seconds: int,
        max_seconds: int,
    ) -> list[HighlightProposal]:
        payload = self.client.chat_json(
            model=model,
            system=SYSTEM_PROMPT,
            user=_user_prompt(chunk, min_seconds, max_seconds),
            temperature=0.2,
        )
        if isinstance(payload, list):
            payload = {"candidates": payload}
        batch = HighlightProposalBatch.model_validate(payload)
        valid: list[HighlightProposal] = []
        for item in batch.candidates:
            duration = item.end_seconds - item.start_seconds
            # Keep slightly outside range; boundary snap will fix when possible.
            if duration < 8 or duration > 45:
                continue
            # Must intersect the current chunk window.
            if item.end_seconds < chunk.start_seconds or item.start_seconds > chunk.end_seconds:
                continue
            valid.append(item)
        return valid


highlight_analyzer = HighlightAnalyzer()
