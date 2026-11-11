"""Versioned per-clip configuration contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CONFIG_SCHEMA_VERSION = 1

AspectKey = Literal["9:16", "1:1", "16:9", "4:3", "4:5", "21:9", "custom"]
ResolutionLabel = Literal["480p", "720p", "1080p", "1440p", "2160p", "custom"]
QualityPreset = Literal["fast", "balanced", "high", "custom"]
VideoCodec = Literal["h264", "h265"]
EncoderPref = Literal["auto", "nvenc", "cpu"]
ReframeMode = Literal[
    "auto",
    "smart_crop",
    "center_crop",
    "blurred_bg",
    "solid_bg",
    "original",
    "manual",
    "podcast",
    "gaming",
    "tutorial",
    "educational",
    "general",
]
SubtitleAnimation = Literal[
    "word",
    "karaoke",
    "pop",
    "fade",
    "scale",
    "static",
    "punch",
]
SubtitlePosition = Literal["top", "center", "bottom", "custom"]


class SubtitleSegmentOverride(BaseModel):
    text: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, value: float, info) -> float:  # type: ignore[no-untyped-def]
        start = info.data.get("start")
        if start is not None and value <= float(start):
            raise ValueError("segment end must be greater than start")
        return value


class SubtitleStyleConfig(BaseModel):
    font_family: str = "Montserrat"
    font_size: int = Field(default=64, ge=12, le=200)
    font_weight: Literal["normal", "bold"] = "bold"
    text_color: str = "#FFFFFF"
    highlight_color: str = "#FFE600"
    outline_color: str = "#000000"
    outline_width: int = Field(default=3, ge=0, le=12)
    shadow: int = Field(default=2, ge=0, le=12)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    alignment: Literal["left", "center", "right"] = "center"
    position: SubtitlePosition = "bottom"
    custom_vertical: float = Field(default=0.85, ge=0.0, le=1.0)
    margin_h: int = Field(default=40, ge=0, le=400)
    max_chars_per_line: int = Field(default=28, ge=8, le=80)
    max_lines: int = Field(default=2, ge=1, le=4)
    animation: SubtitleAnimation = "word"
    uppercase: bool = False
    safe_area: Literal["none", "tiktok", "reels", "shorts"] = "tiktok"


class SubtitleConfig(BaseModel):
    enabled: bool = True
    preset_slug: str = "hormozi"
    style: SubtitleStyleConfig = Field(default_factory=SubtitleStyleConfig)
    segments: list[SubtitleSegmentOverride] | None = None


class ManualCrop(BaseModel):
    """Normalized crop rectangle (0-1 relative to source frame)."""

    x: float = Field(default=0.0, ge=0.0, le=1.0)
    y: float = Field(default=0.0, ge=0.0, le=1.0)
    width: float = Field(default=1.0, gt=0.0, le=1.0)
    height: float = Field(default=1.0, gt=0.0, le=1.0)


class ReframeConfig(BaseModel):
    mode: ReframeMode = "auto"
    background_color: str = "#000000"
    focal_x: float = Field(default=0.5, ge=0.0, le=1.0)
    focal_y: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_face_detection: bool = True
    manual_crop: ManualCrop | None = None


class VideoConfig(BaseModel):
    aspect_ratio: AspectKey = "9:16"
    resolution_label: ResolutionLabel = "1080p"
    width: int = Field(default=1080, ge=16, le=7680)
    height: int = Field(default=1920, ge=16, le=7680)
    fps: int | None = Field(default=30, ge=1, le=120)
    preserve_source_fps: bool = False
    quality_preset: QualityPreset = "balanced"
    crf: int = Field(default=18, ge=12, le=36)
    codec: VideoCodec = "h264"
    encoder: EncoderPref = "auto"


class AudioExportConfig(BaseModel):
    codec: Literal["aac"] = "aac"
    bitrate_kbps: int = Field(default=192, ge=64, le=512)
    volume: float = Field(default=1.0, ge=0.0, le=2.0)


class ExportConfig(BaseModel):
    container: Literal["mp4"] = "mp4"
    filename_pattern: str = "{title}_{id8}"
    output_directory: str | None = None


class ClipConfiguration(BaseModel):
    schema_version: int = CONFIG_SCHEMA_VERSION
    subtitles: SubtitleConfig = Field(default_factory=SubtitleConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    reframe: ReframeConfig = Field(default_factory=ReframeConfig)
    audio: AudioExportConfig = Field(default_factory=AudioExportConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    profile_id: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sync_dimensions(self) -> ClipConfiguration:
        from app.media.aspect import dimensions_for_aspect

        if self.video.aspect_ratio != "custom" and self.video.resolution_label != "custom":
            width, height = dimensions_for_aspect(
                self.video.aspect_ratio,
                resolution_label=self.video.resolution_label,
                custom_width=self.video.width,
                custom_height=self.video.height,
            )
            self.video.width = width
            self.video.height = height
        return self


class ClipConfigurationPatch(BaseModel):
    """Partial update; nested models replace wholesale when provided."""

    subtitles: SubtitleConfig | None = None
    video: VideoConfig | None = None
    reframe: ReframeConfig | None = None
    audio: AudioExportConfig | None = None
    export: ExportConfig | None = None
    profile_id: str | None = None
    apply_profile: bool = False


class ApplyConfigurationRequest(BaseModel):
    clip_ids: list[str] = Field(min_length=1)
    configuration: ClipConfigurationPatch
    confirm_overwrite: bool = False


class ClipConfigurationOut(BaseModel):
    clip_id: str
    configuration: ClipConfiguration
    source_width: int | None = None
    source_height: int | None = None
    source_fps: float | None = None
    estimated_file_size_bytes: int | None = None
    validation: dict[str, Any] = Field(default_factory=dict)


class ExportProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str | None = None
    description: str | None = None
    config_json: ClipConfiguration
    is_builtin: bool = False


class ExportProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    config_json: ClipConfiguration | None = None


class ExportProfileOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    config_json: dict[str, Any]
    is_builtin: bool
    created_at: str
    updated_at: str


class PreviewClipRequest(BaseModel):
    configuration: ClipConfigurationPatch | None = None
    save_configuration: bool = True


class BatchRenderRequest(BaseModel):
    clip_ids: list[str] = Field(min_length=1)
    configuration: ClipConfigurationPatch | None = None
    apply_to_all: bool = False
    confirm_overwrite: bool = False
