"""FFmpeg-based audio mixing filtergraph builder with optional sidechain ducking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.media.audio.audio_ducking import sidechain_compress_filter
from app.media.audio.audio_normalizer import alimiter_filter, loudnorm_filter
from app.media.audio.audio_tracks import AudioTrackConfig


@dataclass
class MixPlan:
    filter_complex: str
    output_map: str
    input_files: list[str]


def _volume_expr(track: AudioTrackConfig) -> str:
    if track.muted:
        return "0"
    return f"{track.volume}"


def _process_track(
    track: AudioTrackConfig,
    source: str,
    label: str,
    *,
    clip_duration: float | None,
) -> str:
    """
    Build a per-track audio filter ending in [label].

    Always atrim to the clip window so a long replacement file cannot stretch
    the export past clip.duration_seconds.
    """
    start = max(0.0, float(track.start_seconds or 0.0))
    end = track.end_seconds
    if end is None and clip_duration is not None:
        end = float(clip_duration)
    if end is not None:
        end = max(start + 0.05, float(end))

    if end is not None:
        chain = (
            f"{source}atrim=start={start:.3f}:end={end:.3f},"
            f"asetpts=PTS-STARTPTS,volume={_volume_expr(track)}"
        )
    else:
        chain = f"{source}volume={_volume_expr(track)}"

    if track.fade_in_seconds > 0:
        chain += f",afade=t=in:st=0:d={track.fade_in_seconds}"
    if track.fade_out_seconds > 0 and end is not None:
        fade_start = max(float(end) - float(track.fade_out_seconds) - start, 0.0)
        chain += f",afade=t=out:st={fade_start:.3f}:d={track.fade_out_seconds}"
    if track.offset_seconds:
        delay_ms = int(track.offset_seconds * 1000)
        chain += f",adelay={delay_ms}|{delay_ms}"
    return chain + f"[{label}]"


def build_mix_plan(
    video_input_index: int,
    tracks: list[AudioTrackConfig],
    *,
    enable_loudnorm: bool = True,
    enable_limiter: bool = True,
    ducking: dict[str, Any] | None = None,
    clip_duration: float | None = None,
) -> MixPlan:
    """
    Construct an FFmpeg filter_complex for mixing original/music/voice tracks.

    When music tracks have ducking_enabled and a speech track exists, music is
    sidechain-compressed against the speech bus before the final mix.
    """
    inputs: list[str] = []
    filters: list[str] = []
    next_input = video_input_index + 1

    speech_labels: list[str] = []
    music_labels: list[str] = []
    other_labels: list[str] = []
    duck_music = False

    has_replacement_speech = any(
        t.track_type in {"replacement", "voiceover"} and t.source_path and not t.muted for t in tracks
    )

    duck = ducking or {}
    for index, track in enumerate(tracks):
        # Muted original still had full remaining source length and stretched amix.
        # When a replacement/VO is present, drop the original pad entirely.
        if track.track_type == "original" and track.muted and has_replacement_speech:
            continue

        label = f"a{index}"
        if track.track_type == "original":
            source = f"[{video_input_index}:a]"
        else:
            if not track.source_path:
                continue
            inputs.append(track.source_path)
            source = f"[{next_input}:a]"
            next_input += 1

        filters.append(
            _process_track(track, source, label, clip_duration=clip_duration)
        )
        pad = f"[{label}]"
        if track.track_type in {"original", "voiceover", "replacement"}:
            speech_labels.append(pad)
        elif track.track_type == "music":
            music_labels.append(pad)
            if track.ducking_enabled:
                duck_music = True
        else:
            other_labels.append(pad)

    if not speech_labels and not music_labels and not other_labels:
        filters.append("anullsrc=r=48000:cl=stereo[aout]")
        return MixPlan(filter_complex=";".join(filters), output_map="[aout]", input_files=inputs)

    def _amix(labels: list[str], out: str) -> str:
        if len(labels) == 1:
            return f"{labels[0]}anull{out}"
        # duration=first keeps the mix tied to the first (clip-trimmed) pad,
        # not the longest uploaded file.
        return (
            "".join(labels)
            + f"amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0{out}"
        )

    final_inputs: list[str] = []

    speech_mix_pad: str | None = None
    speech_sc_pad: str | None = None
    if speech_labels:
        filters.append(_amix(speech_labels, "[speech]"))
        if duck_music and music_labels:
            filters.append("[speech]asplit=2[speech_mix][speech_sc]")
            speech_mix_pad = "[speech_mix]"
            speech_sc_pad = "[speech_sc]"
        else:
            speech_mix_pad = "[speech]"
        final_inputs.append(speech_mix_pad)

    if music_labels:
        filters.append(_amix(music_labels, "[musicbus]"))
        if duck_music and speech_sc_pad is not None:
            filters.append(
                sidechain_compress_filter(
                    "[musicbus]",
                    speech_sc_pad,
                    "[ducked]",
                    threshold=float(duck.get("threshold", 0.05)),
                    ratio=float(duck.get("ratio", 6.0)),
                    attack_ms=float(duck.get("attack_ms", 20.0)),
                    release_ms=float(duck.get("release_ms", 250.0)),
                )
            )
            final_inputs.append("[ducked]")
        else:
            final_inputs.append("[musicbus]")

    final_inputs.extend(other_labels)

    if len(final_inputs) == 1:
        mixed = final_inputs[0]
        # Ensure we have a concrete pad name for downstream filters when needed
        if mixed != "[amixed]":
            filters.append(f"{mixed}anull[amixed]")
            mixed = "[amixed]"
    else:
        filters.append(_amix(final_inputs, "[amixed]"))
        mixed = "[amixed]"

    current = mixed
    if enable_loudnorm:
        integrated = float(duck.get("integrated_lufs", -14.0)) if duck else -14.0
        true_peak = float(duck.get("true_peak", -1.5)) if duck else -1.5
        lra = float(duck.get("lra", 11.0)) if duck else 11.0
        filters.append(f"{current}{loudnorm_filter(integrated, true_peak, lra)}[anorm]")
        current = "[anorm]"
    if enable_limiter:
        filters.append(f"{current}{alimiter_filter()}[aout]")
        current = "[aout]"
    elif current != "[aout]":
        filters.append(f"{current}anull[aout]")
        current = "[aout]"

    return MixPlan(
        filter_complex=";".join(filters),
        output_map=current,
        input_files=inputs,
    )
