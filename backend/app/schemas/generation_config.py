"""Pre-processing / clip-generation configuration (before analyze)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.clip_config import (
    AudioExportConfig,
    ClipConfiguration,
    ExportConfig,
    ReframeConfig,
    SubtitleConfig,
    VideoConfig,
)

GENERATION_SCHEMA_VERSION = 1

ContentCategory = Literal[
    "educational",
    "storytelling",
    "podcast",
    "interview",
    "gaming",
    "tutorial",
    "humor",
    "opinions",
    "general",
    "auto",
]
AudioMode = Literal["preserve", "remove", "replace", "music", "voiceover"]
Sensitivity = Literal["low", "medium", "high"]


class GenerationAnalysisConfig(BaseModel):
    language: str | None = None  # null/auto
    whisper_model: str = "small"
    ollama_model: str | None = None
    force_retranscribe: bool = False
    sensitivity: Sensitivity = "medium"
    content_category: ContentCategory = "auto"
    auto_detect_content_type: bool = True


class GenerationDurationConfig(BaseModel):
    min_duration: int = Field(default=12, ge=1, le=120)
    max_duration: int = Field(default=30, ge=1, le=180)
    clip_count: int = Field(default=5, ge=1, le=50)
    auto_clip_count: bool = False


class GenerationAudioConfig(BaseModel):
    mode: AudioMode = "preserve"
    # Integrates with Audio Studio after clips exist; mode is inherited as intent.
    notes: str = ""


class GenerationConfiguration(BaseModel):
    schema_version: int = GENERATION_SCHEMA_VERSION
    duration: GenerationDurationConfig = Field(default_factory=GenerationDurationConfig)
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    reframe: ReframeConfig = Field(default_factory=ReframeConfig)
    audio: GenerationAudioConfig = Field(default_factory=GenerationAudioConfig)
    export_audio: AudioExportConfig = Field(default_factory=AudioExportConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    analysis: GenerationAnalysisConfig = Field(default_factory=GenerationAnalysisConfig)
    profile_id: str | None = None
    profile_slug: str | None = None

    @model_validator(mode="after")
    def _validate_duration(self) -> GenerationConfiguration:
        if self.duration.min_duration > self.duration.max_duration:
            raise ValueError("min_duration cannot be greater than max_duration")
        return self

    def to_clip_configuration(self) -> ClipConfiguration:
        return ClipConfiguration(
            subtitles=self.subtitles,
            video=self.video,
            reframe=self.reframe,
            audio=self.export_audio,
            export=self.export,
            profile_id=self.profile_id,
        )

    def to_analyze_settings(self, *, video_duration: float | None = None) -> dict[str, Any]:
        clip_count = self.duration.clip_count
        if self.duration.auto_clip_count and video_duration:
            # ~1 clip per ~45–60s of source, clamped.
            clip_count = max(3, min(12, int(video_duration / 50) + 2))
        # Sensitivity adjusts requested clip density.
        if self.analysis.sensitivity == "low":
            clip_count = max(1, int(round(clip_count * 0.6)))
        elif self.analysis.sensitivity == "high":
            clip_count = min(50, int(round(clip_count * 1.4)))

        min_duration = self.duration.min_duration
        max_duration = self.duration.max_duration
        if video_duration is not None and video_duration > 0:
            if min_duration > video_duration:
                min_duration = max(1, int(video_duration))
            if max_duration > video_duration:
                max_duration = max(min_duration, int(video_duration))

        ollama = (self.analysis.ollama_model or "").strip() or None
        return {
            "language": None if not self.analysis.language or self.analysis.language == "auto" else self.analysis.language,
            "whisper_model": self.analysis.whisper_model,
            "ollama_model": ollama,
            "force": self.analysis.force_retranscribe,
            "clip_count": clip_count,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "subtitle_preset": self.subtitles.preset_slug,
            "reframing_mode": self.reframe.mode,
            "burn_subtitles": self.subtitles.enabled,
            "content_category": self.analysis.content_category,
            "auto_detect_content_type": self.analysis.auto_detect_content_type,
            "audio_mode": self.audio.mode,
            "generation_config": self.model_dump(),
        }


class GenerationConfigurationOut(BaseModel):
    video_id: str
    configuration: GenerationConfiguration
    validation: dict[str, Any] = Field(default_factory=dict)
    summary: list[str] = Field(default_factory=list)


class GenerationConfigurationPatch(BaseModel):
    configuration: GenerationConfiguration
    apply_profile: bool = False
    profile_id: str | None = None
    confirm_overwrite: bool = False


class GenerationProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str | None = None
    description: str | None = None
    config_json: GenerationConfiguration
    is_builtin: bool = False


class GenerationProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    config_json: GenerationConfiguration | None = None


class GenerationProfileDuplicate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class GenerationProfileOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    config_json: dict[str, Any]
    is_builtin: bool
    created_at: str
    updated_at: str
