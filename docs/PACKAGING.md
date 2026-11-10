# Packaging & Desktop Distribution

## Local development

```powershell
.\scripts\Setup-Dev.ps1
.\scripts\Start-Dev.ps1
```

- Backend: FastAPI on `http://127.0.0.1:8000`
- Angular: `npx ng serve` (or via Start-Dev)
- Tauri: `cd desktop\angular-app && npm run tauri -- dev`

## One-shot Windows release build

Use **Python 3.12** for the backend venv (3.13 may work for packaging, but Faster-Whisper is pinned for 3.12).  
Run the script from a **normal** (non-Administrator) PowerShell window.

```powershell
.\scripts\Build-Release.ps1
```

Flags:

- `-SkipSidecar` — only frontend + Tauri (expects external API)
- `-SkipTauri` — build Angular + PyInstaller sidecar only

What it does:

1. `ng build --configuration=production`
2. PyInstaller onefile → `desktop/angular-app/src-tauri/sidecars/ai-video-clipper-api(.exe)`
3. `tauri build` → NSIS + MSI under `src-tauri/target/release/bundle/`

## Sidecar runtime

On launch, Tauri (`src-tauri/src/lib.rs`) checks `127.0.0.1:8000`. If down, it starts the packaged sidecar from app resources and waits for health. Closing the window kills the child process.

Recommended sidecar env (set automatically / override as needed):

```
AVC_HOST=127.0.0.1
AVC_PORT=8000
AVC_WORKSPACE_PATH=%APPDATA%\AIVideoClipper\workspace
```

## GPU / VRAM (RTX 4070 Ti Super 16GB)

- `GpuManager` serializes Whisper / Ollama ownership and unloads Whisper before LLM / render
- `POST /api/system/gpu/unload-whisper` frees model weights + `torch.cuda.empty_cache()` when available
- Prefer NVENC when FFmpeg lists `h264_nvenc`

## Cache & recovery

- Inventory: `GET /api/system/cache`
- Clear: `POST /api/system/cache/clear` `{ "kind": "all"|"transcription"|"renders"|"audio_extract" }`
- Startup marks leftover `queued`/`running` jobs as `interrupted`
- Retry: `POST /api/jobs/{id}/retry`

## Manual packaging notes

- Bundle FFmpeg (+libass) on PATH or set `AVC_FFMPEG_PATH`
- Install Ollama separately; pull `qwen3:8b` (or configured model)
- Whisper models download on first use into the Faster-Whisper cache
