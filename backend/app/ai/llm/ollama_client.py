"""Local Ollama HTTP client with structured JSON responses."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaError(RuntimeError):
    """Raised when the local Ollama API cannot complete a request."""


def _extract_json_payload(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if not match:
            raise
        return json.loads(match.group(1))


def _is_cuda_failure(status_code: int, body: str) -> bool:
    if status_code < 500:
        return False
    text = (body or "").lower()
    return any(
        token in text
        for token in (
            "cuda error",
            "illegal memory access",
            "cuda_error",
            "out of memory",
            "oom",
            "cublas",
            "cudnn",
        )
    )


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 300.0) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            with httpx.Client(base_url=self.base_url, timeout=2.0) as client:
                response = client.get("/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
        return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]

    def ensure_model(self, model: str) -> str:
        models = self.list_models()
        if model in models:
            return model
        # Accept tag-less / prefix matches (e.g. qwen3:8b vs qwen3:8b-q4_K_M)
        prefix = model.split(":")[0]
        for name in models:
            if name == model or name.startswith(f"{model}") or name.startswith(f"{prefix}:"):
                logger.info("Using available Ollama model '%s' for requested '%s'", name, model)
                return name
        raise OllamaError(
            f"Ollama model '{model}' is not installed. Run: ollama pull {model}. "
            f"Available: {', '.join(models) or 'none'}."
        )

    def chat_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        num_ctx: int | None = None,
        allow_cpu_fallback: bool = True,
    ) -> Any:
        resolved = self.ensure_model(model)
        ctx = int(num_ctx or 4096)
        attempts: list[dict[str, Any]] = [
            {"num_ctx": ctx, "num_gpu": None, "label": "gpu"},
            {"num_ctx": min(ctx, 2048), "num_gpu": None, "label": "gpu-small-ctx"},
        ]
        if allow_cpu_fallback:
            attempts.append({"num_ctx": min(ctx, 2048), "num_gpu": 0, "label": "cpu"})

        last_error: OllamaError | None = None
        for index, attempt in enumerate(attempts):
            options: dict[str, Any] = {
                "temperature": temperature,
                "num_ctx": int(attempt["num_ctx"]),
            }
            if attempt["num_gpu"] is not None:
                options["num_gpu"] = int(attempt["num_gpu"])

            payload = {
                "model": resolved,
                "stream": False,
                "format": "json",
                "options": options,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            logger.debug(
                "Ollama chat model=%s attempt=%s chars=%s options=%s",
                resolved,
                attempt["label"],
                len(user),
                options,
            )
            try:
                with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                    response = client.post("/api/chat", json=payload)
                    if response.status_code >= 400:
                        body = response.text[:1000]
                        err = OllamaError(f"Ollama chat failed ({response.status_code}): {body}")
                        if _is_cuda_failure(response.status_code, body) and index < len(attempts) - 1:
                            logger.warning(
                                "Ollama CUDA/GPU failure on %s; retrying as %s",
                                attempt["label"],
                                attempts[index + 1]["label"],
                            )
                            last_error = err
                            # Brief pause so the runner can recover before CPU fallback.
                            time.sleep(1.5)
                            continue
                        raise err
                    data = response.json()
            except httpx.HTTPError as exc:
                raise OllamaError(f"Ollama request failed: {exc}") from exc

            content = ((data.get("message") or {}).get("content")) or data.get("response") or ""
            if not content:
                last_error = OllamaError("Ollama returned an empty response")
                continue
            try:
                if attempt["label"] != "gpu":
                    logger.info("Ollama chat succeeded via %s fallback", attempt["label"])
                return _extract_json_payload(content)
            except (json.JSONDecodeError, ValueError) as exc:
                raise OllamaError(f"Ollama returned invalid JSON: {content[:1000]}") from exc

        raise last_error or OllamaError("Ollama chat failed after retries")


ollama_client = OllamaClient()
