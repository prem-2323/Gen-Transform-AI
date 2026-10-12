"""Token-budget audit tests (offline, no Ollama/network required)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.token_budgets import (  # noqa: E402
    OUTPUT_BUDGETS,
    TokenBudgetConfig,
    ensure_embedding_budget,
    estimate_tokens,
    get_effective_context_limit,
    get_token_budget_config,
    reset_token_budget_config,
    resolve_output_budget,
    truncate_to_token_budget,
)


def _reset_env(monkeypatch):
    for k in [
        "RAG_MAX_CONTEXT_TOKENS",
        "CONTEXT_BUILDER_MAX_TOKENS",
        "ANALYSIS_MAX_INPUT_TOKENS",
        "EMBEDDING_MAX_TOKENS",
        "OLLAMA_NUM_CTX",
        "SYSTEM_RESERVE_TOKENS",
        "RAG_OUTPUT_RESERVE_TOKENS",
        "STUDENT_MAX_NEW_TOKENS",
        "QWEN_DEFAULT_NUM_PREDICT",
    ]:
        monkeypatch.delenv(k, raising=False)
    reset_token_budget_config()


def test_estimate_tokens_basic_and_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0
    assert estimate_tokens("hello world") >= 2
    # Long English: ~4 chars per token.
    long_en = "word " * 4000  # 20000 chars
    est = estimate_tokens(long_en)
    assert 4000 <= est <= 6000, est


def test_estimate_tokens_multilingual():
    tamil = "தமிழ் மொழி ஆவணம் " * 200
    hindi = "हिन्दी दस्तावेज़ " * 200
    chinese = "中文文档内容" * 300
    for txt in (tamil, hindi, chinese):
        est = estimate_tokens(txt)
        # Must not collapse to word-split undercount; cjk/script chars counted.
        assert est > 100, (txt[:10], est)
        out, info = truncate_to_token_budget(txt, 200, model="t", stage="test")
        assert info["kept_tokens"] <= 200, info
        assert info["truncated"] is True


def test_truncate_long_document_sentence_boundary(monkeypatch):
    _reset_env(monkeypatch)
    doc = " ".join(f"Sentence number {i} states a verified fact about the case." for i in range(500))
    original = estimate_tokens(doc)
    assert original > 3000
    out, info = truncate_to_token_budget(doc, 1000, model="qwen3:4b", stage="test")
    assert info["truncated"] is True
    assert info["kept_tokens"] <= 1000
    assert info["dropped_tokens"] == original - info["kept_tokens"]
    # Head preserved (early relevant facts kept).
    assert "Sentence number 0" in out
    assert "Sentence number 499" not in out


def test_oversized_prompt_context_builder_keeps_head(monkeypatch):
    _reset_env(monkeypatch)
    from app.rag.context_builder import ContextBuilder

    cb = ContextBuilder(max_tokens=500)
    cands = [
        {"document_id": "d", "chunk_id": f"c{i}", "page_number": 1,
         "source": "vector", "source_type": "vector",
         "text": f"Relevant fact {i}. " + ("evidence content " * 60)}
        for i in range(10)
    ]
    ctx, manifest = cb.build_context(query="test", candidates=cands)
    assert len(manifest) < len(cands)  # tail dropped
    assert len(manifest) >= 1  # head kept
    assert manifest[0]["chunk_id"] == "c0"
    assert estimate_tokens(ctx) <= 650  # budget + headers slack


def test_context_builder_default_coordinates_with_rag(monkeypatch):
    monkeypatch.setenv("RAG_MAX_CONTEXT_TOKENS", "3000")
    _reset_env(monkeypatch)
    # Re-read after env set.
    reset_token_budget_config()
    from app.rag.context_builder import ContextBuilder

    cb = ContextBuilder()
    assert cb.max_tokens == 3000
    monkeypatch.setenv("CONTEXT_BUILDER_MAX_TOKENS", "1500")
    reset_token_budget_config()
    cb2 = ContextBuilder()
    assert cb2.max_tokens == 1500


def test_output_budgets_per_deliverable():
    assert resolve_output_budget("executive_summary", None) == OUTPUT_BUDGETS["executive_summary"] == 800
    assert resolve_output_budget("advisory", None) == 2048
    assert resolve_output_budget("presentation", None) == 2048
    assert resolve_output_budget("video_script", None) == 2048
    assert resolve_output_budget("image_prompt", None) == 500
    assert resolve_output_budget("video_plan", None) == 1200
    # Unknown type falls back to default.
    assert resolve_output_budget("unknown_xyz", None) == OUTPUT_BUDGETS["default"]
    # Explicit request clamped to hard cap.
    assert resolve_output_budget("advisory", 999999) == 4096
    # Invalid request falls back.
    assert resolve_output_budget("advisory", -5) == 2048


def test_embedding_inputs_respect_model_limit():
    big = "token " * 2000  # ~2600 tokens
    out, info = ensure_embedding_budget(big, max_tokens=512)
    assert info["truncated"] is True
    assert info["kept_tokens"] <= 510
    # Small input untouched.
    small = "hello world evidence"
    out2, info2 = ensure_embedding_budget(small)
    assert info2["truncated"] is False
    assert out2 == small


def test_chunker_fits_embedding_budget(monkeypatch):
    _reset_env(monkeypatch)
    from app.embeddings.chunker import SemanticChunker
    from app.embeddings.config import EmbeddingConfig

    cfg = EmbeddingConfig(chunk_size=600, max_chunk_size=1200)
    ch = SemanticChunker(config=cfg)
    # Pathological single paragraph (no sentence splits help beyond clamp).
    doc = "Evidence. " + ("word " * 3000)
    chunks = ch.chunk_text(doc, document_id="d1")
    assert len(chunks) >= 1
    for c in chunks:
        assert estimate_tokens(c.text) <= 510, estimate_tokens(c.text)


def test_insufficient_budget_single_head_truncated(monkeypatch):
    _reset_env(monkeypatch)
    from app.rag.context_builder import build_grounded_context

    cands = [{"document_id": "d", "chunk_id": "c0", "text": "word " * 2000}]
    ctx, manifest, _ = build_grounded_context(cands, max_tokens=200)
    assert len(manifest) == 1  # head kept via truncation, not empty
    assert estimate_tokens(ctx) <= 400


def test_effective_rag_budget_reserves_output(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    monkeypatch.setenv("RAG_MAX_CONTEXT_TOKENS", "16000")
    reset_token_budget_config()
    cfg = TokenBudgetConfig()
    eff = cfg.effective_rag_budget()
    # 4096 - 400 - 512 = 3184 usable; must clamp, not blindly use 16000.
    assert eff == 3184, eff
    assert get_token_budget_config().ollama_num_ctx == 4096


def test_effective_context_limit_prefers_runtime(monkeypatch):
    assert get_effective_context_limit("qwen3:4b", ollama_num_ctx=4096) == 4096
    assert get_effective_context_limit("gemini-2.5-flash", ollama_num_ctx=4096) == 4096
    assert get_effective_context_limit("unknown-model-xyz", ollama_num_ctx=4096) == 4096


def test_optimization_config_uses_central_default(monkeypatch):
    monkeypatch.setenv("RAG_MAX_CONTEXT_TOKENS", "2500")
    reset_token_budget_config()
    # Re-import to pick up env (config reads lazily via factory).
    from app.optimization.config import OptimizationConfig

    cfg = OptimizationConfig()
    assert cfg.max_context_tokens == 2500
