# Implementation Plan

## Phase tracking

| Phase | Scope | Status |
|-------|-------|--------|
| 1 Foundation | Repo, backend, Angular/Tauri, SQLite, import + metadata | **Complete** |
| 2 Transcription | Audio extract, Faster-Whisper, word timestamps | Pending approval |
| 3 Highlights | Ollama Qwen3, chunking, scoring, 12–30s clips | Pending |
| 4 Video processing | Clip, ASS subs, reframe, FFmpeg render, batch export | Pending |
| 5 Desktop UI polish | Full screens wired to live endpoints | Partial in Phase 1 |
| 6 Optimization | GPU mgr, cache, cancel/recovery, packaging | Pending |
| Audio Studio | Tracks, mix, ducking, Audio Studio UI | Foundation modules in Phase 1 |

## Phase 1 deliverables

- Project structure and documentation
- FastAPI app with health, dashboard, projects, videos, jobs, settings, WebSocket
- Real FFprobe metadata extraction on import
- SQLite models for all planned entities + Alembic initial migration
- Subtitle preset JSON library
- Audio analyzer + FFmpeg mix/duck/normalize builders
- Angular dark shell with dashboard, import, projects, settings
- Windows PowerShell verify/setup/start scripts

## Phase 1 verification (this environment)

Executed successfully:

- `GET /api/health` — FFmpeg/libass detected; CUDA/Ollama absent → CPU notes
- `POST /api/projects` — project persisted
- `POST /api/videos/import` — sample MP4 stored under `workspace/originals/...`
- Metadata: 1280×720, 30 fps, h264/aac, 16:9
- `POST /api/videos/{id}/analyze` — queued job with stage checklist
- `GET /api/dashboard` + `GET /api/settings`
- `ng build` (Angular 19 development configuration) succeeded

## Phase 2 next (awaiting approval)

1. Extract 16 kHz mono WAV via FFmpeg
2. Run Faster-Whisper (`large-v3` default) with language detection
3. Persist `Transcription` + `TranscriptionWord`
4. Cache transcriptions by video hash/model
5. Wire job manager stage updates over WebSocket

## Blockers observed in this cloud agent environment

- No NVIDIA GPU / CUDA (`nvidia-smi` missing) — CPU path used
- Ollama not installed — not required for Phase 1
- Angular CLI not global — use `npx @angular/cli@19`
- Target OS is Windows 11; this agent runs Linux — scripts are PowerShell for Windows, backend verified on Linux

## Compatibility notes

- Pin Python **3.12** for Faster-Whisper / PyTorch stack
- Prefer `qwen3:8b` via Ollama when available; document fallbacks in `AI_MODELS.md`
- Pyannote may require a Hugging Face token for model download — optional, never mandatory for core clip flow
