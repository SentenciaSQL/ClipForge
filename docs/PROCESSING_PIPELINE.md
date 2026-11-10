# Processing Pipeline

## Stages

| # | Stage | Phase | Engine |
|---|-------|-------|--------|
| 1 | Import | 1 | Filesystem copy |
| 2 | Metadata extraction | 1 | FFprobe |
| 3 | Audio extraction | 2 | FFmpeg |
| 4 | Transcription | 2 | Faster-Whisper |
| 5 | Semantic analysis | 3 | Ollama Qwen3 |
| 6 | Highlight selection | 3 | Scoring + dedupe |
| 7 | Visual analysis | 4 | OpenCV / scene detect |
| 8 | Subtitle generation | 4 | ASS from word timestamps |
| 9 | Rendering | 4 | FFmpeg (+ NVENC when available) |
| 10 | Export | 4 | Copy to `workspace/exports` |

Audio Studio mixing hooks into stage 9 via `app/media/audio`.

## Job lifecycle

```text
queued → running → completed
                 ↘ failed
                 ↘ cancelled
```

Each stage records:

- status
- started/finished timestamps
- message / error
- progress contribution

Jobs persist in SQLite so unexpected shutdowns leave recoverable state.

## Clip constraints

- Duration **12–30 seconds** (configurable within bounds)
- Boundaries snapped to transcript sentence / idea completeness when possible
- Overlapping near-duplicates collapsed; prefer distinct clips
- Scores normalized 0–100 with weighted engagement heuristics

## Rendering defaults

- Container: MP4
- Video: H.264 (NVENC if available)
- Audio: AAC
- Frame size: 1080×1920 (9:16)
- FPS: 30 (or source-driven when required)
- CRF: 18–23 (default 20)

Originals are never overwritten. Intermediates live under `workspace/temporary/`.
