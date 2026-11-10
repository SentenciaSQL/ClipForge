# Implementation Plan

## Phase tracking

| Phase | Scope | Status |
|-------|-------|--------|
| 1 Foundation | Repo, backend, Angular/Tauri, SQLite, import + metadata | **Complete** |
| 2 Transcription | Audio extract, Faster-Whisper, word timestamps | **Complete** |
| 3 Highlights | Ollama Qwen3, chunking, scoring, 12–30s clips | **Complete** |
| 4 Video processing | Clip, ASS subs, reframe, FFmpeg render, batch export | **Complete** |
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

## Phase 2 deliverables

- FFmpeg 16 kHz mono WAV extraction with reuse when source unchanged
- Faster-Whisper integration (`large-v3` default; tiny/base/small/medium/distil supported)
- Auto language detection + word/segment timestamps + confidence
- JSON file cache + SQLite `Transcription` / `TranscriptionWord` persistence
- Background `JobManager` thread pool + GPU lock around Whisper
- `POST /api/videos/{id}/analyze` and `/transcribe` execute real Phase 2 stages
- Job cancellation endpoint
- Angular Import + Generate screens poll live job progress and show transcript

## Phase 3 deliverables

- Ollama client with JSON-mode chat + model availability checks
- Overlapping transcript chunking (≈90s windows / 20s overlap)
- Semantic highlight proposals validated with Pydantic
- Timestamp snapping onto real transcript segments (12–30s)
- Weighted viral-potential scoring + overlap dedupe
- Persist `Highlight` + candidate `Clip` rows
- Analyze jobs now run through highlight selection; later stages deferred
- Angular Clips Studio lists scored candidates; Import/Generate show selected clips

## Phase 4 deliverables

- ASS subtitle generator with word-level highlighting (clip-relative timestamps)
- Reframing modes: auto/smart crop/center crop/blurred background + content profiles
- OpenCV face sampling for smart crop
- FFmpeg renderer (NVENC when available, libx264 fallback) → 1080×1920 MP4
- `POST /api/clips/{id}/render`, `PATCH /api/clips/{id}`, `POST /api/clips/export`
- Clips Studio render controls + Export Library batch export UI

## Phase 5 / Audio Studio next (awaiting approval)

1. Full Audio Studio timeline UI + track APIs
2. Ducking/loudnorm applied during final render
3. Broader desktop polish / packaging

## Blockers observed in this cloud agent environment

- No NVIDIA GPU / CUDA (`nvidia-smi` missing) — CPU path used; Whisper verification uses `small`/`tiny`; Ollama runs on CPU; encoding uses libx264
- Angular CLI not global — use `npx @angular/cli@19`
- Target OS is Windows 11; this agent runs Linux — scripts are PowerShell for Windows, backend verified on Linux

## Compatibility notes

- Pin Python **3.12** for Faster-Whisper / CTranslate2 stack
- Prefer `qwen3:8b` via Ollama when available; document fallbacks in `AI_MODELS.md`
- Pyannote may require a Hugging Face token for model download — optional, never mandatory for core clip flow
