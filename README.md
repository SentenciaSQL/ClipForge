# AI Video Clipper (ClipForge)

Fully local AI-powered video clipping desktop application. Analyze long-form videos, detect engaging moments, generate 12–30s vertical clips with animated subtitles, and export for TikTok, Instagram Reels, and YouTube Shorts — without required cloud APIs.

## Status

Pipeline complete through packaging:

- Import → Faster-Whisper → Ollama highlights → ASS subtitles → smart reframe → audio mix → FFmpeg export
- Audio Studio waveforms, optional speaker diarization
- GPU unload / cache clear / job recovery
- Windows release script (`Build-Release.ps1`) → NSIS/MSI installer

## Repository layout

```text
ClipForge/
├── desktop/angular-app/     # Angular 19 + Tauri 2 (UI + desktop shell)
├── backend/                 # FastAPI + SQLAlchemy + AI/media pipeline
├── resources/               # Subtitle/audio presets, templates
├── workspace/               # Local originals, projects, temp, exports
├── scripts/                 # Windows PowerShell setup / start / release
└── docs/                    # Architecture and phase docs
```

## Requirements

| Component | Notes |
|-----------|--------|
| Windows 11 | Primary target |
| Python **3.12** | Prefer 3.12 (avoid 3.14; 3.13 may work for packaging only) |
| Node.js 20+ | Angular / Tauri frontend |
| Rust + Cargo | Tauri 2 desktop builds |
| FFmpeg + FFprobe | On PATH or configured in Settings |
| Ollama | Local LLM (`qwen3:8b` recommended) |
| NVIDIA CUDA | Optional; CPU fallback supported |

---

## Commands (Windows PowerShell)

Run everything from the repo root unless a command says otherwise:

```powershell
cd C:\Users\PC\Documents\python\ClipForge
```

### 0) PowerShell execution policy (required once)

Windows often blocks unsigned scripts (`Start-Dev.ps1`, `Setup-Dev.ps1`, …) with:

`cannot be loaded. The file is not digitally signed`

**Option A — allow your user to run local scripts (recommended, once):**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Close and reopen PowerShell, then use `.\scripts\...` normally.

**Option B — run one script without changing policy:**

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Verify-Environment.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Setup-Dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Build-Release.ps1
```

**Option C — skip scripts entirely** and use the [manual commands](#manual-start-no-scripts) below.

### 1) Environment file (`.env`)

```powershell
cd C:\Users\PC\Documents\python\ClipForge

# Create .env if missing (Setup-Dev.ps1 also does this)
if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }

# Optional: open it in Notepad
notepad .\.env
```

Important variables (see `.env.example`):

| Variable | Typical value | Notes |
|----------|---------------|--------|
| `AVC_HOST` / `AVC_PORT` | `127.0.0.1` / `8000` | Backend bind |
| `AVC_WORKSPACE_PATH` | `./workspace` | Local media + DB |
| `AVC_CORS_ORIGINS` | `http://127.0.0.1:4200,...` | Angular / Tauri |
| `AVC_FFMPEG_PATH` / `AVC_FFPROBE_PATH` | empty or full `.exe` paths | Leave empty if on PATH |
| `AVC_OLLAMA_URL` / `AVC_OLLAMA_MODEL` | `http://127.0.0.1:11434` / `qwen3:8b` | Local LLM |
| `AVC_WHISPER_MODEL` / `AVC_WHISPER_DEVICE` | e.g. `small` / `auto` | Use `cpu` if CUDA fails |
| `AVC_HF_TOKEN` | optional | Only for pyannote diarization |

### 2) Verify toolchain

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Verify-Environment.ps1
```

### 3) One-time setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Setup-Dev.ps1
```

Creates `.env` (if needed), `backend\.venv`, installs Python deps, and runs `npm install` for Angular.

Then apply DB migrations:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
cd ..
```

### 4) Development mode (browser + API)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1
```

| Service | URL |
|---------|-----|
| Angular UI | http://127.0.0.1:4200 |
| Backend API | http://127.0.0.1:8000 |
| API docs | http://127.0.0.1:8000/docs |

This is the **web UI in the browser** talking to the local FastAPI backend. It does **not** upload anything.

Pull Ollama model once (if using highlights):

```powershell
ollama pull qwen3:8b
```

### Manual start (no scripts)

Use two PowerShell windows. No execution-policy change needed for these commands.

**Terminal 1 — backend**

```powershell
cd C:\Users\PC\Documents\python\ClipForge

if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }

cd backend
py -3.12 -m venv .venv   # only if .venv does not exist yet
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-core.txt
pip install -r requirements.txt
alembic upgrade head
python main.py
# equivalent: uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Angular**

```powershell
cd C:\Users\PC\Documents\python\ClipForge\desktop\angular-app
npm install   # first time only
npm start
```

Then open http://127.0.0.1:4200

### 5) Desktop release build (installer)

Use a **normal** PowerShell window (not Administrator):

```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\Build-Release.ps1
```

What it builds:

1. Angular production bundle → `desktop\angular-app\dist\...` (**embedded into Tauri**, not a separate website deploy)
2. Backend sidecar with PyInstaller → `desktop\angular-app\src-tauri\sidecars\`
3. Tauri Windows installer (NSIS / MSI)

Open the installer folder:

```powershell
explorer .\desktop\angular-app\src-tauri\target\release\bundle\nsis
```

Typical artifact:

```text
AI Video Clipper_0.6.0_x64-setup.exe
```

Also under:

```text
desktop\angular-app\src-tauri\target\release\bundle\msi\
```

Optional flags:

```powershell
.\scripts\Build-Release.ps1 -SkipSidecar   # frontend + Tauri only
.\scripts\Build-Release.ps1 -SkipTauri     # Angular + sidecar only
```

> **Note:** The release app is **desktop**. Angular is included inside the `.exe` window. There is no cloud “upload web” step.

---

## Daily workflow (inside the app)

1. **Import** a video  
2. **Clip Generation** → *Run full analysis* (Whisper + Ollama highlights)  
3. **Clips Studio** → review candidates → *Render 9:16*  
4. **Audio Studio** (optional) → music / ducking / loudnorm → render with mix  
5. **Export Library** → export selected clips  

Outputs land under `workspace\exports\`.

### Optional speaker diarization

Only useful for multi-speaker videos (podcasts / interviews). Not required for the core pipeline.

In **Clip Generation** click **Detect speakers**, or via API:

```powershell
# status
curl http://127.0.0.1:8000/api/diarization/status

# run local engine (no token)
curl -X POST http://127.0.0.1:8000/api/videos/<VIDEO_ID>/diarize `
  -H "Content-Type: application/json" `
  -d "{\"engine\":\"local\",\"max_speakers\":2}"
```

- **local** engine: free, offline, no token  
- **pyannote** engine (optional better quality): install extras + free HF token

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements-optional.txt
```

Token (Hugging Face, free):

1. https://huggingface.co/settings/tokens → create **Read** token  
2. Accept model terms for `pyannote/speaker-diarization-3.1`  
3. Set env:

```powershell
$env:AVC_HF_TOKEN="hf_..."
```

Or in `.env`:

```text
AVC_HF_TOKEN=hf_...
```

`requirements-optional.txt` is **only** for optional extras (pyannote/torch). The core app runs without it.

### Windows GPU (CUDA 12 DLLs for Faster-Whisper)

CTranslate2 needs **`cublas64_12.dll`**. CUDA Toolkit **13.x alone is not enough** (it ships `cublas64_13.dll`).

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements-cuda-windows.txt
```

Restart the backend afterward. ClipForge prepends the pip package `bin` folders to `PATH` automatically. You can keep CUDA 13 installed; just add the CUDA 12 libs via pip (or install Toolkit 12.x alongside).

---

## Environment tips

```powershell
# Activate backend venv (if Activate.ps1 is blocked, use Bypass once)
cd C:\Users\PC\Documents\python\ClipForge\backend
powershell -ExecutionPolicy Bypass -File .\.venv\Scripts\Activate.ps1
# or, after RemoteSigned for CurrentUser:
# .\.venv\Scripts\Activate.ps1

# Confirm env file is loaded from repo root
Get-Content ..\.env | Select-Object -First 20

# Run API alone
python main.py

# Run Angular alone
cd ..\desktop\angular-app
npm start
```

If `Activate.ps1` is blocked and you do not want to change policy, call the venv Python directly:

```powershell
cd C:\Users\PC\Documents\python\ClipForge\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe main.py
```

Workspace paths (created automatically):

```text
workspace\originals\    # imported videos
workspace\projects\     # DB + project audio
workspace\temporary\    # caches, ASS, extracts
workspace\exports\      # rendered MP4s
```

---

## Privacy

All inference and media processing are designed to run locally. Source videos and transcripts are not uploaded automatically. Network is only used when you explicitly download models, npm/pip packages, or Ollama weights.

## Documentation

- **[Guía de uso (con capturas)](docs/USER_GUIDE.md)** ← empieza aquí si es tu primera vez
- [Architecture](docs/ARCHITECTURE.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [API](docs/API.md)
- [AI models](docs/AI_MODELS.md)
- [Windows setup](docs/WINDOWS_SETUP.md)
- [Processing pipeline](docs/PROCESSING_PIPELINE.md)
- [Packaging](docs/PACKAGING.md)
