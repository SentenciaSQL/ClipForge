"""FFmpeg clip renderer: trim, reframe, burn-in ASS, encode."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.hardware import detect_hardware
from app.core.logging import get_logger
from app.media.ffmpeg import get_ffmpeg, run_command
from app.media.reframe import ReframePlan

logger = get_logger(__name__)


@dataclass
class RenderResult:
    output_path: Path
    ass_path: Path | None
    encoder: str
    reframe_mode: str
    command: list[str]


def _escape_subtitles_path(path: Path) -> str:
    # FFmpeg subtitles filter needs escaped special chars, especially on Windows.
    text = path.resolve().as_posix()
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return text


def choose_video_encoder(use_nvenc: str | None = None) -> tuple[str, list[str]]:
    settings = get_settings()
    hardware = detect_hardware()
    preference = (use_nvenc or settings.use_nvenc or "auto").lower()
    want_nvenc = preference in {"auto", "true", "1", "yes"}
    if preference == "false":
        want_nvenc = False
    if want_nvenc and hardware.ffmpeg_has_nvenc and hardware.cuda_available:
        return "h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", str(settings.crf)]
    return "libx264", ["-c:v", "libx264", "-preset", "medium", "-crf", str(settings.crf)]


def render_clip(
    *,
    source_path: Path,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
    reframe: ReframePlan,
    ass_path: Path | None = None,
    fps: int | None = None,
    burn_subtitles: bool = True,
) -> RenderResult:
    settings = get_settings()
    ffmpeg = get_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    encoder_name, encoder_args = choose_video_encoder()
    target_fps = fps or settings.output_fps

    # When reframe uses filtergraph with labels (blurred_bg), use -filter_complex.
    uses_complex = "[" in reframe.filter_chain or ";" in reframe.filter_chain
    args = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(source_path),
        "-t",
        f"{duration_seconds:.3f}",
    ]

    if uses_complex:
        filter_complex = reframe.filter_chain
        if burn_subtitles and ass_path and ass_path.exists():
            escaped = _escape_subtitles_path(ass_path)
            filter_complex = f"{filter_complex}[vtmp];[vtmp]subtitles='{escaped}'[vout]"
            mapped_video = "[vout]"
        else:
            filter_complex = f"{filter_complex}[vout]"
            mapped_video = "[vout]"
        args += ["-filter_complex", filter_complex, "-map", mapped_video, "-map", "0:a?"]
    else:
        video_filter = reframe.filter_chain
        if burn_subtitles and ass_path and ass_path.exists():
            escaped = _escape_subtitles_path(ass_path)
            video_filter = f"{video_filter},subtitles='{escaped}'"
        args += ["-vf", video_filter]

    args += encoder_args
    args += [
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(target_fps),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    logger.info(
        "Rendering clip encoder=%s mode=%s out=%s cmd=%s",
        encoder_name,
        reframe.mode,
        output_path,
        " ".join(shlex.quote(part) for part in args),
    )
    run_command(args, timeout=max(600, int(duration_seconds * 40) + 120))
    return RenderResult(
        output_path=output_path,
        ass_path=ass_path,
        encoder=encoder_name,
        reframe_mode=reframe.mode,
        command=args,
    )
