"""Centralized token-budget policy (single source of truth).

Replaces scattered hardcoded limits:
- ``text[:12000]`` / ``text[:16000]`` character truncation
- ``max_tokens=2000`` / ``3000`` / ``800`` / ``2048`` literals
- char-vs-token confusion in embedding chunk sizes

All budgets are conservative by design: they respect the *runtime*
Ollama ``num_ctx`` (default 4096) rather than the theoretical model
maximum, and they reserve space for system prompts + expected output.

Environment overrides (all optional):
    RAG_MAX_CONTEXT_TOKENS      default 3000  (hard cap 16000)
    CONTEXT_BUILDER_MAX_TOKENS  default unset -> follows RAG_MAX
    ANALYSIS_MAX_INPUT_TOKENS   default 3000  (~12000 chars)
    EMBEDDING_MAX_TOKENS        default 512
    OLLAMA_NUM_CTX              default 4096
    SYSTEM_RESERVE_TOKENS       default 400
    RAG_OUTPUT_RESERVE_TOKENS   default 512
    STUDENT_MAX_NEW_TOKENS      default 2048
    QWEN_DEFAULT_NUM_PREDICT    default 800
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, Optional, Tuple

log = logging.getLogger("gen-transform.token_budgets")

# ---------------------------------------------------------------------------
# Model theoretical limits (for diagnostics only — never auto-applied).
# ---------------------------------------------------------------------------
MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    "qwen3:4b": 32768,          # native; 131072 with YaRN
    "qwen3:4b-yarn": 131072,
    "qwen2.5:3b": 32768,
    "qwen2.5:0.5b": 32768,
    "qwen/qwen2.5-0.5b-instruct": 32768,
    "gemma3:4b": 131072,
    "gemma2:2b": 8192,
    "gemini-2.5-flash": 1048576,
    "bge-small-en-v1.5": 512,
    "baai/bge-small-en-v1.5": 512,
}

MODEL_OUTPUT_LIMITS: Dict[str, int] = {
    "qwen3:4b": 32768,
    "qwen2.5:3b": 8192,
    "qwen/qwen2.5-0.5b-instruct": 8192,
    "gemma3:4b": 8192,
    "gemma2:2b": 4096,
    "gemini-2.5-flash": 65536,
}

RAG_HARD_MAX_TOKENS = 16000
ANALYSIS_HARD_MAX_TOKENS = 16000

# Per-deliverable output budgets (num_predict / max_new_tokens).
# Conservative values sized for local Ollama VRAM + concurrency.
OUTPUT_BUDGETS: Dict[str, int] = {
    "executive_summary": 800,
    "summary": 800,
    "advisory": 2048,
    "advisory_memo": 2048,
    "presentation": 2048,
    "deck": 2048,
    "slides": 2048,
    "video_script": 2048,
    "video": 2048,
    "analysis_report": 3000,
    "cross_validation": 1500,
    "visual_desc": 150,
    "image_prompt": 500,
    "video_plan": 1200,
    "scene": 2000,
    "video_gen": 1024,
    "rag_answer": 512,
    "student": 2048,
    "qwen_default": 800,
    "default": 800,
}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default


# ---------------------------------------------------------------------------
# Token estimation (multilingual-safe, dependency-free).
# ---------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    """Estimate token count without a tokenizer download.

    Uses ``max(chars/4, words*1.3, cjk_chars)`` so space-separated
    (English), agglutinative (Tamil/Hindi/Arabic), and CJK text are all
    conservatively covered. Never returns 0 for non-empty text.
    """
    if not text:
        return 0
    stripped = text.strip()
    if not stripped:
        return 0
    char_est = len(stripped) // 4
    words = stripped.split()
    word_est = int(len(words) * 1.3) if words else 0
    # Scripts without whitespace carry ~1 token per char; count them directly.
    cjk = sum(
        1
        for ch in stripped
        if ("\u4e00" <= ch <= "\u9fff")
        or ("\u0b80" <= ch <= "\u0bff")  # Tamil
        or ("\u0900" <= ch <= "\u097f")  # Devanagari
        or ("\u0600" <= ch <= "\u06ff")  # Arabic
        or ("\u3040" <= ch <= "\u30ff")  # Japanese kana
        or ("\uac00" <= ch <= "\ud7af")  # Korean hangul
    )
    return max(1, char_est, word_est, min(cjk, len(stripped)))


def truncate_to_token_budget(
    text: str,
    max_tokens: int,
    *,
    model: str = "unknown",
    stage: str = "unknown",
    preserve_sentences: bool = True,
) -> Tuple[str, Dict[str, object]]:
    """Truncate *text* to *max_tokens* (estimated) at a sentence boundary.

    Returns ``(truncated_text, info)`` where *info* carries
    ``truncated/original_tokens/kept_tokens/dropped_tokens/model/stage``.
    Logs a warning on truncation so silent evidence loss is visible.
    For inputs > 2x budget an additional hint to use RAG/chunked
    summarization is logged (hierarchical path lives in the RAG pipeline;
    single-pass analysis keeps head content deterministically).
    """
    original_tokens = estimate_tokens(text or "")
    info: Dict[str, object] = {
        "truncated": False,
        "original_tokens": original_tokens,
        "kept_tokens": original_tokens,
        "dropped_tokens": 0,
        "budget": int(max_tokens),
        "model": model,
        "stage": stage,
    }
    if original_tokens <= max_tokens or not text:
        return text or "", info

    target_chars = max(64, int(max_tokens) * 4)
    cut = text[:target_chars]
    if preserve_sentences and len(text) > target_chars:
        for sep in ("\n\n", "\n", ". ", "? ", "! ", "; ", ".", "?", "!", " "):
            idx = cut.rfind(sep)
            # Keep at least half the budget so we don't over-trim.
            if idx > target_chars * 0.5:
                cut = cut[: idx + len(sep)].strip()
                break

    kept = estimate_tokens(cut)
    # Multilingual safety loop: char heuristic can undercount.
    guard = 0
    while kept > max_tokens and len(cut) > 100 and guard < 5:
        cut = cut[: int(len(cut) * max_tokens / max(1, kept) * 0.95)].strip()
        kept = estimate_tokens(cut)
        guard += 1

    info.update(
        {
            "truncated": True,
            "kept_tokens": kept,
            "dropped_tokens": max(0, original_tokens - kept),
        }
    )
    log.warning(
        "token budget truncation stage=%s model=%s original=%d kept=%d dropped=%d budget=%d",
        stage,
        model,
        original_tokens,
        kept,
        info["dropped_tokens"],
        max_tokens,
    )
    if original_tokens > 2 * max_tokens:
        log.warning(
            "input %dx over budget at stage=%s; prefer RAG retrieval / chunked "
            "summarization over single-pass analysis for full coverage",
            round(original_tokens / max(1, max_tokens), 1),
            stage,
        )
    return cut, info


def ensure_embedding_budget(
    text: str, max_tokens: int = 512, reserve: int = 2
) -> Tuple[str, Dict[str, object]]:
    """Clamp *text* to the embedding model's sequence length."""
    usable = max(16, int(max_tokens) - int(reserve))
    return truncate_to_token_budget(
        text, usable, model="embedding", stage="embed", preserve_sentences=False
    )


def resolve_output_budget(
    deliverable: Optional[str] = None,
    requested: Optional[int] = None,
    hard_cap: int = 4096,
) -> int:
    """Resolve per-deliverable ``num_predict`` / ``max_new_tokens``.

    Falls back to ``OUTPUT_BUDGETS['default']`` for unknown types; clamps
    explicit *requested* values to *hard_cap* with a warning.
    """
    key = (deliverable or "default").strip().lower()
    base = OUTPUT_BUDGETS.get(key, OUTPUT_BUDGETS["default"])
    if requested is None:
        return base
    try:
        val = int(requested)
    except (TypeError, ValueError):
        return base
    if val <= 0:
        return base
    if val > hard_cap:
        log.warning(
            "output budget clamped deliverable=%s requested=%d cap=%d",
            key,
            val,
            hard_cap,
        )
        return hard_cap
    return val


def get_effective_context_limit(model_name: str, ollama_num_ctx: Optional[int] = None) -> int:
    """Effective input limit = min(theoretical, Ollama num_ctx)."""
    ctx = ollama_num_ctx if ollama_num_ctx is not None else _int_env("OLLAMA_NUM_CTX", 4096)
    key = (model_name or "").strip().lower()
    theoretical = MODEL_CONTEXT_LIMITS.get(key)
    if theoretical is None:
        # prefix match (e.g. "qwen3:4b" vs "qwen3:4b-q4_k_m")
        for name, limit in MODEL_CONTEXT_LIMITS.items():
            if key.startswith(name.split(":")[0]) and name.split(":")[0]:
                theoretical = limit
                break
    if theoretical is None:
        return int(ctx)
    return min(int(theoretical), int(ctx))


# ---------------------------------------------------------------------------
# Central config object.
# ---------------------------------------------------------------------------
class TokenBudgetConfig:
    """Runtime token budgets; reads env on construction (test-friendly)."""

    def __init__(self) -> None:
        self.rag_max_context_tokens = max(100, _int_env("RAG_MAX_CONTEXT_TOKENS", 3000))
        self.rag_hard_max = RAG_HARD_MAX_TOKENS
        raw_cb = os.getenv("CONTEXT_BUILDER_MAX_TOKENS", "").strip()
        try:
            self.context_builder_max_tokens = int(raw_cb) if raw_cb else None
        except ValueError:
            self.context_builder_max_tokens = None
        self.analysis_max_input_tokens = max(100, _int_env("ANALYSIS_MAX_INPUT_TOKENS", 3000))
        self.embedding_max_tokens = max(64, _int_env("EMBEDDING_MAX_TOKENS", 512))
        self.embedding_reserve_tokens = 2
        self.ollama_num_ctx = max(1024, _int_env("OLLAMA_NUM_CTX", 4096))
        self.system_reserve_tokens = max(0, _int_env("SYSTEM_RESERVE_TOKENS", 400))
        self.rag_output_reserve_tokens = max(0, _int_env("RAG_OUTPUT_RESERVE_TOKENS", 512))
        self.student_max_new_tokens = max(16, _int_env("STUDENT_MAX_NEW_TOKENS", 2048))
        self.qwen_default_num_predict = max(16, _int_env("QWEN_DEFAULT_NUM_PREDICT", 800))

    @property
    def effective_context_builder_tokens(self) -> int:
        """ContextBuilder budget coordinated with the RAG budget."""
        base = (
            self.context_builder_max_tokens
            if self.context_builder_max_tokens is not None
            else self.rag_max_context_tokens
        )
        return max(100, min(int(base), self.rag_hard_max))

    def effective_rag_budget(self) -> int:
        """RAG evidence budget after reserving system + output space."""
        usable = self.ollama_num_ctx - self.system_reserve_tokens - self.rag_output_reserve_tokens
        usable = max(512, usable)
        if self.rag_max_context_tokens > usable:
            log.warning(
                "RAG budget %d exceeds Ollama usable ctx %d (num_ctx=%d reserves=%d); clamping",
                self.rag_max_context_tokens,
                usable,
                self.ollama_num_ctx,
                self.system_reserve_tokens + self.rag_output_reserve_tokens,
            )
            return usable
        return int(self.rag_max_context_tokens)

    def output_budget_for(
        self, deliverable: Optional[str] = None, requested: Optional[int] = None
    ) -> int:
        base = resolve_output_budget(deliverable, None)
        # Honor explicit per-deliverable env overrides is unnecessary; clamp only.
        return resolve_output_budget(deliverable, requested if requested is not None else base)


@lru_cache(maxsize=1)
def get_token_budget_config() -> TokenBudgetConfig:
    return TokenBudgetConfig()


def reset_token_budget_config() -> None:
    get_token_budget_config.cache_clear()


__all__ = [
    "MODEL_CONTEXT_LIMITS",
    "MODEL_OUTPUT_LIMITS",
    "OUTPUT_BUDGETS",
    "RAG_HARD_MAX_TOKENS",
    "ANALYSIS_HARD_MAX_TOKENS",
    "TokenBudgetConfig",
    "estimate_tokens",
    "truncate_to_token_budget",
    "ensure_embedding_budget",
    "resolve_output_budget",
    "get_effective_context_limit",
    "get_token_budget_config",
    "reset_token_budget_config",
]
