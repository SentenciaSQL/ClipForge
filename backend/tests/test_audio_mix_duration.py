"""Replacement audio must not stretch exports past the clip window."""

from __future__ import annotations

from app.media.audio.audio_mixer import build_mix_plan
from app.media.audio.audio_tracks import AudioTrackConfig


def test_mix_plan_atrims_and_skips_muted_original_when_replacement_present():
    tracks = [
        AudioTrackConfig(track_type="original", label="Original", muted=True, volume=0.0, end_seconds=28.0),
        AudioTrackConfig(
            track_type="replacement",
            label="VO",
            source_path="/tmp/long_vo.wav",
            volume=1.0,
            muted=False,
            end_seconds=28.0,
        ),
    ]
    plan = build_mix_plan(0, tracks, enable_loudnorm=False, enable_limiter=False, clip_duration=28.0)
    assert plan.input_files == ["/tmp/long_vo.wav"]
    assert "atrim=start=0.000:end=28.000" in plan.filter_complex
    assert "duration=first" in plan.filter_complex
    # Muted original must not appear as a pad (would stretch amix to source EOF).
    assert "[0:a]" not in plan.filter_complex


def test_mix_plan_keeps_audible_original_without_replacement():
    tracks = [
        AudioTrackConfig(track_type="original", label="Original", muted=False, volume=1.0, end_seconds=12.0),
    ]
    plan = build_mix_plan(0, tracks, enable_loudnorm=False, enable_limiter=False, clip_duration=12.0)
    assert "[0:a]" in plan.filter_complex
    assert "atrim=start=0.000:end=12.000" in plan.filter_complex
