# AI Video Clipper

Fully local AI-powered video clipping desktop application. Analyze long-form videos, detect engaging moments, generate 12–30s vertical clips with animated subtitles, and export for TikTok, Instagram Reels, and YouTube Shorts — without required cloud APIs.

## Status

**Phase 6 — Optimization + packaging: implemented**

Working today:

- Full local pipeline: import → Whisper → Ollama highlights → ASS + reframe → audio mix → FFmpeg export
- GPU manager unloads Whisper before Ollama/render to protect 16GB VRAM workflows
- Cache inventory/clear + interrupted-job recovery + job retry
- Audio Studio + all Angular screens wired to live APIs
- Tauri sidecar bootstrap and `scripts/Build-Release.ps1` for Windows NSIS/MSI builds

Also available: Audio Studio waveform timelines and optional local speaker diarization (no paid APIs).

See `docs/PACKAGING.md` for release steps.

## Repository layout

```text
ai-video-clipper/
├── desktop/angular-app/     # Angular 19 + Tauri 2
├── backend/                 # FastAPI + SQLAlchemy + AI/media pipeline
├── resources/               # Subtitle presets, fonts, templates
├── workspace/               # Local originals, projects, temp, exports
├── scripts/                 # Windows PowerShell setup/start scripts
└── docs/                    # Architecture and phase docs
```

## Quick start (Windows PowerShell)

```powershell
# 1) Verify toolchain
.\scripts\Verify-Environment.ps1

# 2) One-time setup
.\scripts\Setup-Dev.ps1

# 3) Start backend + Angular
.\scripts\Start-Dev.ps1
```

Backend: `http://127.0.0.1:8000`  
API docs: `http://127.0.0.1:8000/docs`  
Angular: `http://127.0.0.1:4200`

## Requirements

| Component | Notes |
|-----------|--------|
| Windows 11 | Primary target |
| Python 3.12 | Required (avoid 3.14 for AI deps) |
| Node.js 20+ | Angular / Tauri frontend |
| Rust + Cargo | Tauri 2 |
| FFmpeg + FFprobe | On PATH or configured in settings |
| Ollama | Local LLM (Phase 3+); optional for Phase 1 |
| NVIDIA CUDA | Optional; CPU fallback supported |

Copy `.env.example` → `.env` before first run.

## Privacy

All inference and media processing are designed to run locally. Source videos and transcripts are not uploaded automatically. Network access is only used when you explicitly download models or dependencies.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [API](docs/API.md)
- [AI models](docs/AI_MODELS.md)
- [Windows setup](docs/WINDOWS_SETUP.md)
- [Processing pipeline](docs/PROCESSING_PIPELINE.md)
