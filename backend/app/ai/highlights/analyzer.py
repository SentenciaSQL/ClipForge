"""Semantic highlight detection via local Ollama models."""

from __future__ import annotations

from typing import Any

from app.ai.highlights.boundaries import snap_window
from app.ai.highlights.dedupe import RankedCandidate, select_distinct_candidates
from app.ai.highlights.heuristic import build_heuristic_candidates
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
- Also work for trailers, cinematic dialogue, ads, music beds, rhythm edits, and sparse speech.
- Spoken words are NOT required. Music, lyrics-as-atmosphere, beats, and visual moments are valid clips (audio may be replaced externally later).
- Always propose at least 1 candidate for the window when there is any content (speech OR timed segments). Prefer striking lines when present; otherwise propose the strongest 12–30s pacing windows.
- category MUST be one of: hook, story, advice, educational, controversial, emotional, funny, revelation, qa, conclusion, memorable, general.
- Candidate duration should target 12 to 30 seconds (wall-clock; silence/music between lines is OK).
- Use timestamps that refer to the absolute times provided in the transcript window.
- Scores are 0-100 estimates of engagement potential, not guaranteed virality.
"""


_CONTENT_CATEGORY_HINTS: dict[str, str] = {
    "educational": "Prefer clear explanations, definitions, and teachable takeaways.",
    "storytelling": "Prefer narrative arcs, setups, and punchy story beats.",
    "podcast": "Prefer conversational moments, guest reactions, and quotable dialogue.",
    "interview": "Prefer Q&A exchanges, surprising answers, and strong guest statements.",
    "gaming": "Prefer hype moments, reactions, clutch plays, and commentary peaks.",
    "tutorial": "Prefer step-by-step instructions and actionable how-to segments.",
    "humor": "Prefer jokes, punchlines, awkward beats, and laugh-out-loud moments.",
    "opinions": "Prefer strong takes, debates, and contrarian viewpoints.",
    "general": "Balance hooks, emotion, clarity, and standalone value.",
    "auto": "Infer the content type from the transcript and adapt selection accordingly.",
}


def _user_prompt(
    chunk: TranscriptChunk,
    min_seconds: int,
    max_seconds: int,
    *,
    content_category: str = "auto",
) -> str:
    hint = _CONTENT_CATEGORY_HINTS.get(content_category, _CONTENT_CATEGORY_HINTS["auto"])
    lines = [
        f"Window {chunk.index}: {chunk.start_seconds:.2f}s → {chunk.end_seconds:.2f}s",
        f"Target clip duration: {min_seconds}-{max_seconds} seconds.",
        f"Content focus: {content_category}. {hint}",
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
    lines.append(
        "Return 1-5 candidates for this window. Spoken words are optional — "
        "music/rhythm/visual moments are valid. Only return an empty array if the window is unusable."
    )
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
        content_category: str = "auto",
    ) -> list[RankedCandidate]:
        settings = get_settings()
        model_name = model or settings.ollama_model
        category = (content_category or "auto").strip().lower() or "auto"
        if not self.client.is_available():
            raise OllamaError(
                f"Ollama is not reachable at {self.client.base_url}. Start Ollama and pull {model_name}."
            )

        chunks = chunk_segments(segments, window_seconds=90.0, overlap_seconds=20.0)

        effective_min = min_seconds
        effective_max = max_seconds
        if video_duration is not None:
            effective_max = min(max_seconds, max(int(video_duration), min(min_seconds, int(video_duration) or min_seconds)))
            if video_duration < min_seconds:
                logger.info(
                    "Video duration %.1fs is shorter than preferred minimum %ss; allowing shorter full-length clips",
                    video_duration,
                    min_seconds,
                )
                effective_min = max(1, int(video_duration))

        raw_candidates: list[RankedCandidate] = []
        chunk_failures = 0
        for chunk in chunks:
            try:
                proposals = self._analyze_chunk(
                    chunk,
                    model=model_name,
                    min_seconds=effective_min,
                    max_seconds=effective_max,
                    content_category=category,
                )
            except OllamaError as exc:
                chunk_failures += 1
                logger.warning(
                    "Ollama failed on highlight chunk %s (%s); continuing with remaining chunks",
                    chunk.index,
                    exc,
                )
                continue
            for proposal in proposals:
                snapped = snap_window(
                    segments,
                    proposal.start_seconds,
                    proposal.end_seconds,
                    min_seconds=float(effective_min),
                    max_seconds=float(effective_max),
                    video_duration=video_duration,
                    min_words=0,
                )
                if not snapped:
                    logger.info(
                        "Rejected proposal outside bounds: %.2f-%.2f",
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
                hook = proposal.hook.strip() or (text[:120] if text else f"Moment {start:.0f}s–{end:.0f}s")
                raw_candidates.append(
                    RankedCandidate(
                        start_seconds=round(start, 3),
                        end_seconds=round(end, 3),
                        duration_seconds=round(end - start, 3),
                        transcript=text,
                        hook=hook,
                        category=proposal.category,
                        description=proposal.description.strip(),
                        reason=proposal.reason.strip(),
                        score=scored.score,
                        score_breakdown=scored.breakdown,
                        source_chunk=chunk.index,
                    )
                )

        selected = select_distinct_candidates(raw_candidates, max_count=max(1, clip_count))
        if not selected:
            logger.warning(
                "Ollama produced 0 usable clips (raw=%s, chunk_failures=%s); "
                "running speech-optional heuristic fallback",
                len(raw_candidates),
                chunk_failures,
            )
            selected = build_heuristic_candidates(
                segments,
                clip_count=clip_count,
                min_seconds=float(effective_min),
                max_seconds=float(effective_max),
                video_duration=video_duration,
            )
            if not selected and chunk_failures and chunk_failures >= max(1, len(chunks)):
                raise OllamaError(
                    "Ollama CUDA/GPU failed on every highlight chunk and heuristic fallback "
                    "also found no clips. Restart Ollama (or set a smaller model) and retry."
                )
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
        content_category: str = "auto",
    ) -> list[HighlightProposal]:
        payload = self.client.chat_json(
            model=model,
            system=SYSTEM_PROMPT,
            user=_user_prompt(chunk, min_seconds, max_seconds, content_category=content_category),
            temperature=0.2,
        )
        if isinstance(payload, list):
            payload = {"candidates": payload}
        raw_items = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(raw_items, list):
            # Fall back to strict batch parse for odd shapes.
            try:
                batch = HighlightProposalBatch.model_validate(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Ignoring invalid highlight payload for chunk %s: %s", chunk.index, exc)
                return []
            raw_items = [item.model_dump() for item in batch.candidates]

        valid: list[HighlightProposal] = []
        for raw in raw_items:
            try:
                item = HighlightProposal.model_validate(raw)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping invalid highlight candidate in chunk %s: %s", chunk.index, exc)
                continue
            duration = item.end_seconds - item.start_seconds
            # Allow short seeds; snap_window expands into the 12–30s target range.
            if duration < 2 or duration > 60:
                continue
            # Must intersect the current chunk window.
            if item.end_seconds < chunk.start_seconds or item.start_seconds > chunk.end_seconds:
                continue
            valid.append(item)
        return valid


highlight_analyzer = HighlightAnalyzer()
