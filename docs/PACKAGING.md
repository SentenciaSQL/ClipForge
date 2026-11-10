# Packaging & Desktop Distribution

## Local development

```powershell
.\scripts\Setup-Dev.ps1
.\scripts\Start-Dev.ps1
```

- Backend: FastAPI on `http://127.0.0.1:8000`
- Angular: `npx ng serve` (or via Start-Dev)
- Tauri: `cd desktop/src-tauri && cargo tauri dev` when Rust toolchain is present

## Windows production build (target machine)

1. Install Node 20+, Rust stable, WebView2, FFmpeg (with libass), Ollama, CUDA toolkit (optional for RTX).
2. Build Angular:

```powershell
cd desktop\angular-app
npm ci
npx ng build --configuration=production
```

3. Build Tauri installer:

```powershell
cd desktop
npm run tauri build
```

Artifacts land under `desktop/src-tauri/target/release/bundle/` (MSI / NSIS).

4. Bundle Python backend options:
   - **Dev-adjacent**: ship `backend/` + `.venv` and launch uvicorn from Tauri sidecar.
   - **Packaged**: PyInstaller onepass for `backend/main.py` as `ai-video-clipper-api.exe`, register as Tauri sidecar.

Recommended sidecar env:

```
AVC_HOST=127.0.0.1
AVC_PORT=8000
AVC_WORKSPACE_PATH=%APPDATA%\AIVideoClipper\workspace
```

## GPU / VRAM notes (RTX 4070 Ti Super 16GB)

- Whisper `large-v3` + float16 fits alone; keep `JobManager.gpu_lock` so Whisper and Ollama never overlap.
- Prefer NVENC (`h264_nvenc`) when `ffmpeg -encoders` lists it.
- Cache Whisper transcripts under `workspace/temporary/` to avoid re-transcription.

## Recovery

- Cancel jobs via `POST /api/jobs/{id}/cancel`
- Failed renders leave ASS under `workspace/temporary/.../renders/` for inspection
- Re-run `POST /api/clips/{id}/render` after Audio Studio mix changes
