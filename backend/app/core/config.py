"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    # backend/app/core/config.py → repo root is parents[3]
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration for the local AI Video Clipper backend."""

    model_config = SettingsConfigDict(
        env_file=str(_repo_root() / ".env"),
        env_file_encoding="utf-8",
        env_prefix="AVC_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    database_url: str = ""
    workspace_path: Path = Field(default_factory=lambda: _repo_root() / "workspace")
    cors_origins: str = (
        "http://localhost:4200,http://127.0.0.1:4200,"
        "tauri://localhost,http://tauri.localhost"
    )

    def model_post_init(self, __context: object) -> None:
        if not self.database_url:
            db_path = self.workspace_path / "projects" / "ai_video_clipper.db"
            self.database_url = f"sqlite:///{db_path.as_posix()}"
            return

        # Resolve relative sqlite paths against the repo root so CWD does not matter.
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix) :]
            path = Path(raw)
            if not path.is_absolute():
                path = (_repo_root() / path).resolve()
                self.database_url = f"sqlite:///{path.as_posix()}"

    ffmpeg_path: str = ""
    ffprobe_path: str = ""

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"

    whisper_model: str = "large-v3"
    whisper_device: Literal["auto", "cuda", "cpu"] = "auto"
    whisper_compute_type: str = "auto"

    prefer_gpu: bool = True
    max_concurrent_jobs: int = 1
    use_nvenc: Literal["auto", "true", "false"] = "auto"

    output_width: int = 1080
    output_height: int = 1920
    output_fps: int = 30
    crf: int = 20
    clip_min_seconds: int = 12
    clip_max_seconds: int = 30

    @field_validator("workspace_path", mode="before")
    @classmethod
    def _resolve_workspace(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = _repo_root() / path
        return path.resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def originals_dir(self) -> Path:
        return self.workspace_path / "originals"

    @property
    def projects_dir(self) -> Path:
        return self.workspace_path / "projects"

    @property
    def temporary_dir(self) -> Path:
        return self.workspace_path / "temporary"

    @property
    def exports_dir(self) -> Path:
        return self.workspace_path / "exports"

    def ensure_directories(self) -> None:
        for directory in (
            self.workspace_path,
            self.originals_dir,
            self.projects_dir,
            self.temporary_dir,
            self.exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
