"""Sidechain ducking filter builders for background music under speech."""

from __future__ import annotations


def sidechain_compress_filter(
    music_label: str,
    speech_label: str,
    output_label: str,
    threshold: float = 0.05,
    ratio: float = 6.0,
    attack_ms: float = 20.0,
    release_ms: float = 250.0,
) -> str:
    """
    Build an FFmpeg sidechaincompress filter.

    music_label/speech_label are filtergraph pad names such as '[bg]' and '[voice]'.
    """
    return (
        f"{music_label}{speech_label}sidechaincompress="
        f"threshold={threshold}:ratio={ratio}:attack={attack_ms}:release={release_ms}"
        f"{output_label}"
    )
