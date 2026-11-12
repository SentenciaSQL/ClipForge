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
    quality_preset: str = "balanced"
    crf_or_cq: int | None = None


def _escape_subtitles_path(path: Path) -> str:
    text = path.resolve().as_posix()
    text = text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return text


def video_opacity_filter(opacity: float | None) -> str | None:
    """
    Dim the video frame toward black without touching later ASS burn-in.

    colorchannelmixer scales RGB toward 0 (= black). Applied after reframe and
    before subtitles= so captions stay fully opaque.
    """
    if opacity is None:
        return None
    value = max(0.0, min(1.0, float(opacity)))
    if value >= 0.999:
        return None
    # Keep three decimals for stable filter graphs / cache keys.
    scaled = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"colorchannelmixer=rr={scaled}:gg={scaled}:bb={scaled}"


def _append_video_effects(
    chain: str,
    *,
    opacity: float | None,
    ass_path: Path | None,
    burn_subtitles: bool,
    complex_graph: bool,
) -> str:
    """
    Append opacity (optional) then subtitles to a reframe chain.

    Order is always: reframe → opacity → subtitles, so captions stay opaque.
    complex_graph=True builds a filter_complex fragment; False builds -vf commas.
    """
    opacity_filter = video_opacity_filter(opacity)
    burn = bool(burn_subtitles and ass_path and ass_path.exists())
    escaped = _escape_subtitles_path(ass_path) if burn and ass_path else None

    if complex_graph:
        if opacity_filter and burn and escaped:
            return (
                f"{chain}[vbase];"
                f"[vbase]{opacity_filter}[vdim];"
                f"[vdim]subtitles='{escaped}'[vout]"
            )
        if opacity_filter:
            return f"{chain}[vbase];[vbase]{opacity_filter}[vout]"
        if burn and escaped:
            return f"{chain}[vtmp];[vtmp]subtitles='{escaped}'[vout]"
        return f"{chain}[vout]"

    filters = [chain]
    if opacity_filter:
        filters.append(opacity_filter)
    if burn and escaped:
        filters.append(f"subtitles='{escaped}'")
    return ",".join(filters)


def choose_video_encoder(
    *,
    use_nvenc: str | None = None,
    codec: str = "h264",
    quality_preset: str = "balanced",
    crf: int | None = None,
) -> tuple[str, list[str], int]:
    """
    Return (encoder_name, ffmpeg_args, effective_crf_or_cq).

    NVENC CQ is not identical to x264 CRF; we only use NVENC when hardware supports it
    and the user preference allows it. CPU libx264 often looks better at similar CQ numbers.
    """
    settings = get_settings()
    hardware = detect_hardware()
    preference = (use_nvenc or settings.use_nvenc or "auto").lower()
    want_nvenc = preference in {"auto", "true", "1", "yes", "nvenc"}
    if preference in {"false", "cpu"}:
        want_nvenc = False

    quality = (quality_preset or "balanced").lower()
    # Map named profiles → CRF/CQ + presets.
    # Draft/fast: speed. Balanced: default. High: CRF ~18. Maximum: slow + lower CRF.
    crf_value = int(crf if crf is not None else settings.crf)
    if quality in {"draft", "fast"}:
        crf_value = min(28, max(crf_value, 18) + 4)
        x264_preset = "veryfast"
        nvenc_preset = "p1"
        x264_tune: list[str] = []
    elif quality in {"maximum", "max"}:
        crf_value = max(14, min(crf_value, 17))
        x264_preset = "veryslow"
        nvenc_preset = "p7"
        x264_tune = ["-tune", "film"]
    elif quality == "high":
        crf_value = max(15, min(crf_value, 18))
        x264_preset = "slow"
        nvenc_preset = "p6"
        x264_tune = []
    else:  # balanced / custom
        crf_value = max(16, min(crf_value, 20)) if quality == "balanced" else crf_value
        x264_preset = "medium"
        nvenc_preset = "p4"
        x264_tune = []

    codec_name = (codec or "h264").lower()
    nvenc_ok = bool(hardware.ffmpeg_has_nvenc and hardware.cuda_available)
    if want_nvenc and nvenc_ok:
        if codec_name == "h265":
            return (
                "hevc_nvenc",
                [
                    "-c:v",
                    "hevc_nvenc",
                    "-preset",
                    nvenc_preset,
                    "-rc",
                    "vbr",
                    "-cq",
                    str(crf_value),
                    "-b:v",
                    "0",
                    "-spatial-aq",
                    "1",
                    "-temporal-aq",
                    "1",
                ],
                crf_value,
            )
        return (
            "h264_nvenc",
            [
                "-c:v",
                "h264_nvenc",
                "-preset",
                nvenc_preset,
                "-rc",
                "vbr",
                "-cq",
                str(crf_value),
                "-b:v",
                "0",
                "-spatial-aq",
                "1",
                "-temporal-aq",
                "1",
            ],
            crf_value,
        )

    if want_nvenc and not nvenc_ok:
        logger.info("NVENC requested/auto but unavailable — using CPU encoder")

    if codec_name == "h265":
        return (
            "libx265",
            ["-c:v", "libx265", "-preset", x264_preset, "-crf", str(crf_value)],
            crf_value,
        )
    return (
        "libx264",
        ["-c:v", "libx264", "-preset", x264_preset, "-crf", str(crf_value), *x264_tune],
        crf_value,
    )


def render_clip(
    *,
    source_path: Path,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
    reframe: ReframePlan,
    ass_path: Path | None = None,
    fps: int | None = None,
    preserve_source_fps: bool = False,
    burn_subtitles: bool = True,
    mix_plan: MixPlan | None = None,
    codec: str = "h264",
    encoder: str = "auto",
    quality_preset: str = "balanced",
    crf: int | None = None,
    audio_bitrate_kbps: int = 192,
    video_opacity: float = 1.0,
) -> RenderResult:
    settings = get_settings()
    ffmpeg = get_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    encoder_name, encoder_args, effective_q = choose_video_encoder(
        use_nvenc=encoder,
        codec=codec,
        quality_preset=quality_preset,
        crf=crf,
    )
    uses_complex_video = "[" in reframe.filter_chain or ";" in reframe.filter_chain
    apply_mix = mix_plan is not None and bool(mix_plan.filter_complex)

    # Seek + duration MUST both be input options on the source (-ss/-t before -i).
    # When mix inputs follow, a lone -t after the first -i would attach to the
    # replacement file instead of capping the video — that made 28s clips export
    # at full remaining source length (often minutes).
    dur = f"{max(0.05, float(duration_seconds)):.3f}"
    args = [
        ffmpeg,
        "-hide_banner",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-t",
        dur,
        "-i",
        str(source_path),
    ]

    if apply_mix:
        for extra in mix_plan.input_files:
            # Cap each mix input to the clip window as well.
            args += ["-t", dur, "-i", str(extra)]

    if uses_complex_video or apply_mix:
        if uses_complex_video:
            video_graph = _append_video_effects(
                reframe.filter_chain,
                opacity=video_opacity,
                ass_path=ass_path,
                burn_subtitles=burn_subtitles,
                complex_graph=True,
            )
        else:
            video_filter = _append_video_effects(
                reframe.filter_chain,
                opacity=video_opacity,
                ass_path=ass_path,
                burn_subtitles=burn_subtitles,
                complex_graph=False,
            )
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
        video_filter = _append_video_effects(
            reframe.filter_chain,
            opacity=video_opacity,
            ass_path=ass_path,
            burn_subtitles=burn_subtitles,
            complex_graph=False,
        )
        args += ["-vf", video_filter]

    args += encoder_args
    args += [
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        f"{int(audio_bitrate_kbps)}k",
        # Hard output duration + shortest stream — belt and suspenders with atrim.
        "-t",
        dur,
        "-shortest",
        "-movflags",
        "+faststart",
    ]

    # Avoid FPS interpolation unless the user requested a specific rate.
    # Do not pass -vsync: recent FFmpeg builds removed it ("Unrecognized option 'vsync'").
    # Omitting -r preserves the source timing; -r only when an explicit FPS is requested.
    if not (preserve_source_fps or fps is None) and fps is not None:
        args += ["-r", str(int(fps))]

    args.append(str(output_path))

    logger.info(
        "Rendering clip encoder=%s q=%s mode=%s upscale=%s mix=%s burn_subs=%s out=%s cmd=%s",
        encoder_name,
        effective_q,
        reframe.mode,
        reframe.linear_upscale,
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
        quality_preset=quality_preset,
        crf_or_cq=effective_q,
    )
