"""text/qwen_service.py — Qwen via local Ollama for image & video prompt pipelines.

Single source of truth for prompt-engineering calls made from
``image/prompt_engine.py`` and ``video/planner.py``.

Contract used by those modules:
    generate_with_qwen(prompt, num_predict=..., timeout=...) -> str
    QwenServiceError
"""

from __future__ import annotations

import logging
import re
import os
from typing import Optional

log = logging.getLogger("gen-transform.text.qwen_service")

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/generate"
DEFAULT_MODEL = os.getenv("TEXT_MODEL") or "qwen2.5:3b"



def _default_num_predict() -> int:
    try:
        import os

        return max(16, int(os.getenv("QWEN_DEFAULT_NUM_PREDICT", "800")))
    except (TypeError, ValueError):
        return 800


DEFAULT_NUM_PREDICT = _default_num_predict()
DEFAULT_TIMEOUT = 120.0


class QwenServiceError(Exception):
    """Raised when the local Qwen (Ollama) service is unavailable or fails."""


def _strip_think(raw: str) -> str:
    """Remove Qwen3 ``<think>...</think>`` blocks and code fences."""
    cleaned = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def generate_with_qwen(
    prompt: str,
    model: str = DEFAULT_MODEL,
    num_predict: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
    temperature: float = 0.3,
    deliverable: Optional[str] = None,
) -> str:
    """Send a prompt to local Ollama Qwen and return cleaned text.

    ``num_predict`` defaults to the centralized ``QWEN_DEFAULT_NUM_PREDICT``
    (800); pass ``deliverable`` (e.g. ``"image_prompt"``) to resolve a
    per-deliverable budget. Signature remains backward compatible:
    positional ``num_predict`` still works; ``None`` means default.
    """
    if num_predict is None:
        effective_predict = _default_num_predict()
        # Per-deliverable override when requested without explicit budget.
        if deliverable:
            try:
                import sys
                from pathlib import Path

                _backend = Path(__file__).resolve().parent.parent
                if str(_backend) not in sys.path:
                    sys.path.insert(0, str(_backend))
                from app.core.token_budgets import resolve_output_budget

                effective_predict = resolve_output_budget(deliverable, None)
            except Exception:
                pass
    else:
        try:
            effective_predict = max(16, int(num_predict))
        except (TypeError, ValueError):
            effective_predict = _default_num_predict()
    try:
        _words = len((prompt or "").split())
        _chars = len(prompt or "")
        log.info(
            "text.qwen_generate model=%s prompt_chars=%d prompt_words=%d num_predict=%d",
            model,
            _chars,
            _words,
            effective_predict,
        )
    except Exception:
        pass
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - requests ships with backend deps
        raise QwenServiceError("The 'requests' package is not installed.") from exc

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,  # disable Qwen3 extended thinking for clean output
        "options": {
            "num_predict": int(effective_predict),
            "temperature": float(temperature),
        },
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=(5.0, float(timeout)),
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise QwenServiceError("Ollama timed out while generating text.") from exc
    except requests.exceptions.RequestException as exc:
        raise QwenServiceError(f"Ollama is unavailable: {exc}") from exc

    raw = (response.json().get("response") or "").strip()
    if not raw:
        raise QwenServiceError("Qwen returned an empty response.")
    return _strip_think(raw)


def is_qwen_available(timeout: float = 1.5) -> bool:
    """Cheap probe so callers can degrade gracefully when Ollama is offline."""
    try:
        import requests

        response = requests.get(
            "http://localhost:11434/api/tags", timeout=float(timeout)
        )
        return response.status_code == 200
    except Exception:
        return False
