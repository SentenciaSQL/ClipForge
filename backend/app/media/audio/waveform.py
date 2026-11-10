"""Compute lightweight waveform peak envelopes for UI timelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def compute_peaks(
    audio_path: Path | str,
    *,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
    num_peaks: int = 480,
) -> dict[str, Any]:
    """
    Return normalized absolute peak samples for drawing a waveform.

    Uses max-abs buckets so the UI can render without shipping raw PCM.
    """
    import soundfile as sf

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio not found: {path}")

    with sf.SoundFile(str(path)) as handle:
        sample_rate = int(handle.samplerate)
        total_frames = len(handle)
        start_frame = max(0, int(start_seconds * sample_rate))
        if duration_seconds is None:
            stop_frame = total_frames
        else:
            stop_frame = min(total_frames, start_frame + max(int(duration_seconds * sample_rate), 1))
        if start_frame >= stop_frame:
            return {
                "peaks": [0.0] * num_peaks,
                "sample_rate": sample_rate,
                "start_seconds": start_seconds,
                "duration_seconds": 0.0,
                "path": str(path),
            }
        handle.seek(start_frame)
        frames = handle.read(stop_frame - start_frame, dtype="float32", always_2d=False)

    if getattr(frames, "ndim", 1) > 1:
        frames = np.mean(frames, axis=1)
    audio = np.asarray(frames, dtype=np.float32)
    duration = float(len(audio) / sample_rate) if sample_rate else 0.0
    if len(audio) == 0:
        peaks = [0.0] * num_peaks
    else:
        bucket = max(len(audio) // num_peaks, 1)
        peaks_arr = []
        for index in range(num_peaks):
            chunk = audio[index * bucket : (index + 1) * bucket]
            if len(chunk) == 0:
                peaks_arr.append(0.0)
            else:
                peaks_arr.append(float(np.max(np.abs(chunk))))
        peak_max = max(peaks_arr) or 1.0
        peaks = [round(value / peak_max, 4) for value in peaks_arr]

    return {
        "peaks": peaks,
        "sample_rate": sample_rate,
        "start_seconds": float(start_seconds),
        "duration_seconds": duration,
        "path": str(path),
    }
