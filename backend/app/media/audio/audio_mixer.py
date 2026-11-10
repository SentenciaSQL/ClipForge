"""FFmpeg-based audio mixing filtergraph builder."""

from __future__ import annotations

from dataclasses import dataclass

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


def build_mix_plan(
    video_input_index: int,
    tracks: list[AudioTrackConfig],
    *,
    enable_loudnorm: bool = True,
    enable_limiter: bool = True,
) -> MixPlan:
    """
    Construct an FFmpeg filter_complex for mixing original/music/voice tracks.

    Phase 1 provides the real filter builder. Full clip render wiring uses this
    in Phase 4 / Audio Studio integration.
    """
    inputs: list[str] = []
    filters: list[str] = []
    mix_labels: list[str] = []
    next_input = video_input_index + 1

    for index, track in enumerate(tracks):
        label = f"a{index}"
        if track.track_type == "original":
            source = f"[{video_input_index}:a]"
        else:
            if not track.source_path:
                continue
            inputs.append(track.source_path)
            source = f"[{next_input}:a]"
            next_input += 1

        chain = [f"{source}volume={_volume_expr(track)}"]
        if track.fade_in_seconds > 0:
            chain.append(f"afade=t=in:st=0:d={track.fade_in_seconds}")
        if track.fade_out_seconds > 0 and track.end_seconds is not None:
            start = max(track.end_seconds - track.fade_out_seconds, 0)
            chain.append(f"afade=t=out:st={start}:d={track.fade_out_seconds}")
        if track.offset_seconds:
            delay_ms = int(track.offset_seconds * 1000)
            chain.append(f"adelay={delay_ms}|{delay_ms}")

        filters.append(",".join(chain) + f"[{label}]")
        mix_labels.append(f"[{label}]")

    if not mix_labels:
        # Silent track fallback
        filters.append("anullsrc=r=48000:cl=stereo[aout]")
        return MixPlan(filter_complex=";".join(filters), output_map="[aout]", input_files=inputs)

    if len(mix_labels) == 1:
        mixed = mix_labels[0]
    else:
        filters.append(
            "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:normalize=0[amixed]"
        )
        mixed = "[amixed]"

    current = mixed
    if enable_loudnorm:
        filters.append(f"{current}{loudnorm_filter()}[anorm]")
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
