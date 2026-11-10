"""Optional speaker diarization."""

from app.ai.diarization.service import DiarizationResult, diarize_audio, pyannote_available

__all__ = ["DiarizationResult", "diarize_audio", "pyannote_available"]
