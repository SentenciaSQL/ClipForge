"""FFmpeg clip renderer: trim, reframe, burn-in ASS, mix audio, encode."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.hardware import detect_hardware
from app.core.logging import get_logger
from app.media.audio.audio_mixer import MixPlan
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
    mix_applied: bool = False


def _escape_subtitles_path(path: Path) -> str:
    text = path.resolve().as_posix()
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return text


def choose_video_encoder(
    *,
    use_nvenc: str | None = None,
    codec: str = "h264",
    quality_preset: str = "balanced",
    crf: int | None = None,
) -> tuple[str, list[str]]:
    settings = get_settings()
    hardware = detect_hardware()
    preference = (use_nvenc or settings.use_nvenc or "auto").lower()
    want_nvenc = preference in {"auto", "true", "1", "yes", "nvenc"}
    if preference in {"false", "cpu"}:
        want_nvenc = False

    quality = (quality_preset or "balanced").lower()
    crf_value = int(crf if crf is not None else settings.crf)
    if quality == "fast":
        crf_value = min(28, crf_value + 4)
        x264_preset = "veryfast"
        nvenc_preset = "p1"
    elif quality == "high":
        crf_value = max(14, crf_value - 2)
        x264_preset = "slow"
        nvenc_preset = "p6"
    else:
        x264_preset = "medium"
        nvenc_preset = "p4"

    codec_name = (codec or "h264").lower()
    if want_nvenc and hardware.ffmpeg_has_nvenc and hardware.cuda_available:
        if codec_name == "h265":
            return (
                "hevc_nvenc",
                ["-c:v", "hevc_nvenc", "-preset", nvenc_preset, "-rc", "vbr", "-cq", str(crf_value)],
            )
        return (
            "h264_nvenc",
            ["-c:v", "h264_nvenc", "-preset", nvenc_preset, "-rc", "vbr", "-cq", str(crf_value)],
        )

    if codec_name == "h265":
        return "libx265", ["-c:v", "libx265", "-preset", x264_preset, "-crf", str(crf_value)]
    return "libx264", ["-c:v", "libx264", "-preset", x264_preset, "-crf", str(crf_value)]


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
    mix_plan: MixPlan | None = None,
    codec: str = "h264",
    encoder: str = "auto",
    quality_preset: str = "balanced",
    crf: int | None = None,
    audio_bitrate_kbps: int = 192,
) -> RenderResult:
    settings = get_settings()
    ffmpeg = get_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    encoder_name, encoder_args = choose_video_encoder(
        use_nvenc=encoder,
        codec=codec,
        quality_preset=quality_preset,
        crf=crf,
    )
    target_fps = fps or settings.output_fps
    uses_complex_video = "[" in reframe.filter_chain or ";" in reframe.filter_chain
    apply_mix = mix_plan is not None and bool(mix_plan.filter_complex)

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

    if apply_mix:
        for extra in mix_plan.input_files:
            args += ["-i", str(extra)]

    if uses_complex_video or apply_mix:
        if uses_complex_video:
            video_graph = reframe.filter_chain
            if burn_subtitles and ass_path and ass_path.exists():
                escaped = _escape_subtitles_path(ass_path)
                video_graph = f"{video_graph}[vtmp];[vtmp]subtitles='{escaped}'[vout]"
            else:
                video_graph = f"{video_graph}[vout]"
        else:
            video_filter = reframe.filter_chain
            if burn_subtitles and ass_path and ass_path.exists():
                escaped = _escape_subtitles_path(ass_path)
                video_filter = f"{video_filter},subtitles='{escaped}'"
            video_graph = f"[0:v]{video_filter}[vout]"

        if apply_mix:
            filter_complex = f"{video_graph};{mix_plan.filter_complex}"
            args += [
                "-filter_complex",
                filter_complex,
                "-map",
                "[vout]",
                "-map",
                mix_plan.output_map,
            ]
        else:
            args += ["-filter_complex", video_graph, "-map", "[vout]", "-map", "0:a?"]
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
        f"{int(audio_bitrate_kbps)}k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    logger.info(
        "Rendering clip encoder=%s mode=%s mix=%s burn_subs=%s out=%s cmd=%s",
        encoder_name,
        reframe.mode,
        apply_mix,
        burn_subtitles,
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
        mix_applied=apply_mix,
    )
