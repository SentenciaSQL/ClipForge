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

## Verify

```powershell
cd path\to\ai-video-clipper
.\scripts\Verify-Environment.ps1
```

## Setup

```powershell
Copy-Item .env.example .env
.\scripts\Setup-Dev.ps1
```

This creates `backend\.venv`, installs Python deps, and installs Angular npm packages.

Optional Ollama model:

```powershell
ollama pull qwen3:8b
```

## Start development

```powershell
.\scripts\Start-Dev.ps1
```

Or separately:

```powershell
# Terminal 1 — backend
cd backend
.\.venv\Scripts\Activate.ps1
python main.py

# Terminal 2 — Angular
cd desktop\angular-app
npm start
```

## Tauri desktop window

```powershell
cd desktop\angular-app
npm run tauri dev
```

## Common issues

| Issue | Fix |
|-------|-----|
| `python` not found | Reinstall Python 3.12 with PATH enabled; or use `py -3.12` |
| FFmpeg missing | Install FFmpeg and restart the terminal |
| CUDA not detected | Update NVIDIA driver; backend falls back to CPU |
| Ollama unreachable | Start Ollama service; set `AVC_OLLAMA_URL` |
| Port 8000 in use | Change `AVC_PORT` in `.env` |
| Angular build errors | Ensure Node 20+; delete `node_modules` and reinstall |

## Paths

Use Windows paths in `.env` if overriding workspace/FFmpeg:

```env
AVC_WORKSPACE_PATH=C:\Users\You\Videos\ai-video-clipper-workspace
AVC_FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
AVC_FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
```
