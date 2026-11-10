# AI Models

All models run locally. No paid cloud API keys are required.

## Transcription — Faster-Whisper

| Model | VRAM (approx) | Notes |
|-------|---------------|-------|
| `large-v3` | ~3–5 GB | Default quality target |
| `distil-large-v3` | lower | Faster alternative |
| `medium` | ~1.5–3 GB | Balanced |
| `small` | ~1 GB | Low-resource fallback |

Device selection: `auto` → CUDA if available, else CPU.  
Compute type: `auto` (float16 on GPU, int8/float32 on CPU as appropriate).

## Semantic analysis — Ollama

| Model | Role |
|-------|------|
| `qwen3:8b` | Default highlight / hook analysis |

Install:

```powershell
ollama pull qwen3:8b
```

If `qwen3:8b` is unavailable in your Ollama registry, use the closest available Qwen3 8B tag and set `AVC_OLLAMA_MODEL` accordingly. Document the exact tag in Settings.

## Speaker diarization — optional

Pyannote Audio when installed and authorized. The core pipeline must succeed without it.

## Vision

OpenCV for faces/scenes. Optional local vision models later; never required for Phase 1–3 text pipeline.

## VRAM management

- Hold a process-wide GPU lock around Whisper / LLM / vision loads.
- Prefer sequential stages over concurrent large models.
- Unload / release models between stages when memory is constrained.

## Downloads

Model downloads happen only when the user installs Ollama models or when Faster-Whisper pulls weights on first use. Source videos and transcripts never leave the machine automatically.
