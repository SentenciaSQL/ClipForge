# AI Models

All models run locally. No paid cloud API keys are required.

## Transcription — Faster-Whisper

| Model | VRAM (approx) | Notes |
|-------|---------------|-------|
| `large-v3` | ~3–5 GB | Default quality target |
| `distil-large-v3` | lower | Faster alternative |
| `medium` | ~1.5–3 GB | Balanced |
| `small` | ~1 GB | Low-resource / CPU-friendly |
| `tiny` / `base` | minimal | Smoke tests and weak CPUs |

Device selection: `auto` → CUDA if available, else CPU.  
Compute type: `auto` (`float16` on GPU, `int8` on CPU).

Audio is extracted with FFmpeg to 16 kHz mono WAV, then loaded with `soundfile` into float32 PCM before Whisper (avoids PyAV version drift).  
VAD uses Faster-Whisper’s built-in Silero VAD filter (`vad_filter=True`).  
Transcription JSON caches live under `workspace/temporary/{video_id}/transcription_cache/`.

## Semantic analysis — Ollama

| Model | Role |
|-------|------|
| `qwen3:8b` | Default highlight / hook analysis |

Install:

```powershell
ollama pull qwen3:8b
```

If `qwen3:8b` is unavailable in your Ollama registry, use the closest available Qwen3 8B tag and set `AVC_OLLAMA_MODEL` accordingly. Document the exact tag in Settings.

Phase 3 sends overlapping transcript windows (about 90s with 20s overlap) to `/api/chat` with `format=json`.  
Responses are validated with Pydantic (`HighlightProposalBatch`). LLM timestamps are never trusted blindly — they are snapped onto real Whisper segment boundaries and filtered to 12–30 seconds before scoring.

## Speaker diarization — optional

Two engines:

| Engine | Cost | Requirements |
|--------|------|--------------|
| `local` (default fallback) | Free, offline | NumPy only — spectral/energy clustering |
| `pyannote` | Free local inference | Optional `pyannote.audio` + free HF token to download weights once (`AVC_HF_TOKEN`) |

`POST /api/videos/{id}/diarize` with `{ "engine": "auto"|"local"|"pyannote" }`.  
Core clip pipeline succeeds without diarization. Speaker labels are written onto transcript words/segments when available.

## Vision

OpenCV for faces/scenes. Optional local vision models later; never required for Phase 1–3 text pipeline.

## VRAM management

- Hold a process-wide GPU lock around Whisper / LLM / vision loads.
- Prefer sequential stages over concurrent large models.
- Unload / release models between stages when memory is constrained.

## Downloads

Model downloads happen only when the user installs Ollama models or when Faster-Whisper pulls weights on first use. Source videos and transcripts never leave the machine automatically.
