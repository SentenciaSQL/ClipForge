# Windows Setup

Target: Windows 11 with optional NVIDIA CUDA + Ollama.

## Prerequisites

1. **Python 3.12** — install from python.org; check “Add to PATH”.
2. **Node.js 20+ LTS**
3. **Git**
4. **Rust** — https://rustup.rs (required for Tauri)
5. **Visual Studio Build Tools** — C++ workload (Tauri / native deps)
6. **WebView2** — usually preinstalled on Windows 11
7. **FFmpeg** — download a full build, add `ffmpeg.exe` and `ffprobe.exe` to PATH
8. **Ollama** — https://ollama.com (Phase 3+)
9. **NVIDIA drivers + CUDA** — optional but recommended for RTX 4070 Ti Super

## PowerShell execution policy

If scripts fail with *not digitally signed* / `PSSecurityException`:

```powershell
# Once per Windows user (recommended)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Or bypass for a single run
powershell -ExecutionPolicy Bypass -File .\scripts\Setup-Dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1
```

You can also skip scripts and use the manual commands in the [README](../README.md#manual-start-no-scripts).

## Verify

```powershell
cd C:\Users\PC\Documents\python\ClipForge
powershell -ExecutionPolicy Bypass -File .\scripts\Verify-Environment.ps1
```

## Environment (`.env`)

```powershell
cd C:\Users\PC\Documents\python\ClipForge
if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }
notepad .\.env
```

`Setup-Dev.ps1` creates `.env` automatically if it is missing. Edit paths for FFmpeg / workspace when needed:

```env
AVC_WORKSPACE_PATH=C:\Users\You\Videos\ai-video-clipper-workspace
AVC_FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
AVC_FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
AVC_PORT=8000
AVC_OLLAMA_URL=http://127.0.0.1:11434
AVC_OLLAMA_MODEL=qwen3:8b
```

## Setup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Setup-Dev.ps1
```

This creates `backend\.venv`, installs Python deps, and installs Angular npm packages.

Apply database migrations:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
cd ..
```

Optional Ollama model:

```powershell
ollama pull qwen3:8b
```

## Start development

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-Dev.ps1
```

Or separately (no script / no Bypass needed for `python` / `npm`):

```powershell
# Terminal 1 — backend
cd C:\Users\PC\Documents\python\ClipForge
if (-not (Test-Path .\.env)) { Copy-Item .\.env.example .\.env }
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python main.py

# Terminal 2 — Angular
cd C:\Users\PC\Documents\python\ClipForge\desktop\angular-app
npm start
```

If `Activate.ps1` is also blocked:

```powershell
cd C:\Users\PC\Documents\python\ClipForge\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe main.py
```

## Tauri desktop window

```powershell
cd desktop\angular-app
npm run tauri dev
```

## Common issues

| Issue | Fix |
|-------|-----|
| Script not digitally signed | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` or `powershell -ExecutionPolicy Bypass -File ...` |
| `python` not found | Reinstall Python 3.12 with PATH enabled; or use `py -3.12` |
| FFmpeg missing | Install FFmpeg and restart the terminal |
| CUDA not detected | Update NVIDIA driver; backend falls back to CPU |
| Ollama unreachable | Start Ollama service; set `AVC_OLLAMA_URL` in `.env` |
| Port 8000 in use | Change `AVC_PORT` in `.env` |
| Angular build errors | Ensure Node 20+; delete `node_modules` and reinstall |
| Missing tables / schema | `cd backend` → activate venv → `alembic upgrade head` |
