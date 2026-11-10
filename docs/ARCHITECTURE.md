# Architecture

## Overview

AI Video Clipper is a **modular monolith**:

- **Desktop shell** — Tauri 2 hosts an Angular 19 SPA.
- **Local backend** — FastAPI process on `127.0.0.1` owns persistence, FFmpeg jobs, and AI orchestration.
- **Workspace** — filesystem store for originals, intermediates, and exports.
- **SQLite** — project/job/clip state that survives restarts.

No microservices. No Docker requirement. No mandatory cloud APIs.

## Layers

```text
Angular UI (signals + feature modules)
        │  REST + WebSocket
FastAPI API routers
        │
Services / Orchestrator
        │
AI modules │ Media (FFmpeg) │ Scoring │ Storage
        │
SQLAlchemy / SQLite     workspace/ filesystem
```

## Backend packages

| Package | Responsibility |
|---------|----------------|
| `app/api` | REST + WebSocket |
| `app/core` | Settings, logging, hardware detection |
| `app/database` | SQLAlchemy models + session |
| `app/services` | Use-case logic |
| `app/orchestrator` | Job manager, GPU lock, stage runners |
| `app/ai` | Whisper, Ollama, diarization, vision |
| `app/media` | FFmpeg metadata, clip render, audio mix |
| `app/scoring` | Viral-potential weighted scoring |
| `app/storage` | Safe paths under `workspace/` |
| `app/schemas` | Pydantic contracts |

## Desktop packages

Feature-based Angular standalone components:

- `dashboard`, `projects`, `video-import`, `clip-generation`
- `clips-studio`, `subtitle-editor`, `export-library`, `settings`
- `audio-studio` (UI lands with Audio Studio phase)

Shared: API client, layout shell, design tokens (dark theme).

## Hardware adaptation

On startup the backend probes:

- FFmpeg / FFprobe availability and NVENC / libass
- NVIDIA GPU via `nvidia-smi`
- Ollama `/api/tags`
- CPU / RAM

Recommendations:

- Prefer sequential VRAM-heavy stages (GPU lock).
- Default `max_concurrent_jobs = 1` on consumer GPUs.
- CPU fallback for Whisper and encoding when CUDA/NVENC missing.

## Data flow (Phase 1)

1. UI uploads video → `POST /api/videos/import`
2. Backend stores file under `workspace/originals/{project_id}/`
3. FFprobe extracts metadata → SQLite `source_videos`
4. Dashboard/settings/projects read live DB state

## Decisions

1. **FFmpeg primary** — never MoviePy as the render engine.
2. **ASS + libass** — word-level subtitle styling.
3. **Ollama local API only** — no OpenAI/Anthropic/Gemini requirement.
4. **SQLAlchemy + Alembic** — schema evolves with phases.
5. **Audio Studio** shares `app/media/audio` with the render pipeline (no duplicate FFmpeg wrappers).
