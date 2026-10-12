"""Phase 7 Grounded RAG Context Builder.

Formats QUBO-selected evidence candidates into structured [E1], [E2]... blocks for the QLoRA student prompt,
preserving document ID, page numbers, chunk IDs, and verbatim source text.

Token budgeting (centralized — see ``app.core.token_budgets``):
- :class:`ContextBuilder` defaults to the coordinated RAG budget
  (``RAG_MAX_CONTEXT_TOKENS``, default 3000, hard cap 16000) instead of a
  stale ``2000`` literal, so evidence selection (QUBO) and context building
  share one policy.
- Candidates are consumed in rank order (relevant facts first); overflow is
  dropped from the tail with an explicit warning — never silently.
- A single oversized head candidate is token-truncated rather than dropping
  everything.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.token_budgets import (
    estimate_tokens,
    get_token_budget_config,
    truncate_to_token_budget,
)

log = logging.getLogger("gen-transform.rag.context_builder")


def _format_block(idx: int, item: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
    evidence_id = f"E{idx}"
    doc_id = str(item.get("document_id") or "doc_unknown")
    chunk_id = str(item.get("chunk_id") or item.get("source_id") or item.get("id") or f"chunk_{idx}")
    try:
        page_num = int(item.get("page_number") or item.get("page") or 1)
    except (TypeError, ValueError):
        page_num = 1
    source = str(item.get("source") or item.get("retrieval_method") or item.get("source_type") or "hybrid")
    text = str(item.get("text") or "").strip()
    try:
        rrf_score = float(item.get("rrf_score") or item.get("score") or 0.0)
    except (TypeError, ValueError):
        rrf_score = 0.0
    qubo_sel = bool(item.get("selected_by_qubo", True))
    stype = item.get("source_type") or (
        "graph" if "--[" in text or "rel_" in str(chunk_id) or str(chunk_id).startswith("r") else "vector"
    )
    block = (
        f"[{evidence_id}]\n"
        f"Document: {doc_id}\n"
        f"Page: {page_num}\n"
        f"Chunk: {chunk_id}\n"
        f"Source: {source}\n"
        f"Text: {text}"
    )
    evidence_obj = {
        "evidence_id": evidence_id,
        "document_id": doc_id,
        "chunk_id": chunk_id,
        "page_number": page_num,
        "source": source,
        "text": text,
        "rrf_score": round(rrf_score, 6),
        "qubo_selected": qubo_sel,
        "source_type": stype,
    }
    return block, evidence_obj, stype


def build_grounded_context(
    selected_candidates: List[Dict[str, Any]],
    max_tokens: Optional[int] = None,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build structured grounded context string and evidence manifest.

    Args:
        selected_candidates: rank-ordered evidence dicts (relevant first).
        max_tokens: optional evidence token budget. ``None`` (default)
            preserves the legacy unbounded behaviour for direct callers;
            :class:`ContextBuilder` always passes an explicit budget.

    Returns:
      - formatted_context: Context string formatted as [E1], [E2]... blocks
      - evidence_manifest: List of structured evidence objects (kept only)
      - citations_map: Map of evidence_id -> metadata
    """
    if not selected_candidates:
        return (
            "NO_EVIDENCE_PROVIDED: No relevant source evidence was retrieved or selected.",
            [],
            {},
        )

    # Legacy path: no budget enforcement (backward compatible).
    if max_tokens is None:
        vector_blocks: List[str] = []
        graph_blocks: List[str] = []
        evidence_manifest: List[Dict[str, Any]] = []
        citations_map: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(selected_candidates, start=1):
            block, evidence_obj, stype = _format_block(idx, item)
            (graph_blocks if stype == "graph" else vector_blocks).append(block)
            evidence_manifest.append(evidence_obj)
            citations_map[evidence_obj["evidence_id"]] = evidence_obj
        sections = ["SOURCE INFORMATION: Grounded Context"]
        sections.append("DOCUMENT EVIDENCE:\n" + ("\n\n".join(vector_blocks) if vector_blocks else "None"))
        sections.append("GRAPH EVIDENCE:\n" + ("\n\n".join(graph_blocks) if graph_blocks else "None"))
        return "\n\n".join(sections), evidence_manifest, citations_map

    # Budgeted path: rank-ordered fill with tail-drop + logging.
    budget = max(100, int(max_tokens))
    vector_blocks = []
    graph_blocks = []
    evidence_manifest = []
    citations_map = {}
    # Fixed section overhead so evidence + headers fit the budget.
    overhead = estimate_tokens("SOURCE INFORMATION: Grounded Context\nDOCUMENT EVIDENCE:\nGRAPH EVIDENCE:")
    used = overhead
    dropped = 0
    total_input_tokens = 0
    out_idx = 0

    for item in selected_candidates:
        block, evidence_obj, stype = _format_block(out_idx + 1, item)
        block_tokens = estimate_tokens(block)
        total_input_tokens += block_tokens
        if used + block_tokens > budget:
            # Head-item oversize: truncate its text instead of returning empty.
            if out_idx == 0:
                allowed = max(64, budget - used - estimate_tokens("[E1]\nDocument: x\nPage: 1\nChunk: x\nSource: x\nText: "))
                trunc_text, info = truncate_to_token_budget(
                    str(item.get("text") or ""),
                    allowed,
                    model="rag-context",
                    stage="context_builder",
                )
                item = dict(item)
                item["text"] = trunc_text
                block, evidence_obj, stype = _format_block(1, item)
                block_tokens = estimate_tokens(block)
                if used + block_tokens > budget:
                    dropped += 1
                    continue
            else:
                dropped += 1
                continue
        out_idx += 1
        # Re-number after potential head truncation.
        block, evidence_obj, stype = _format_block(out_idx, item)
        (graph_blocks if stype == "graph" else vector_blocks).append(block)
        evidence_manifest.append(evidence_obj)
        citations_map[evidence_obj["evidence_id"]] = evidence_obj
        used += estimate_tokens(block)

    sections = ["SOURCE INFORMATION: Grounded Context"]
    sections.append("DOCUMENT EVIDENCE:\n" + ("\n\n".join(vector_blocks) if vector_blocks else "None"))
    sections.append("GRAPH EVIDENCE:\n" + ("\n\n".join(graph_blocks) if graph_blocks else "None"))
    formatted_context = "\n\n".join(sections)

    log.info(
        "context_builder budget=%d used=%d input_items=%d kept=%d dropped=%d input_tokens=%d",
        budget,
        used,
        len(selected_candidates),
        len(evidence_manifest),
        dropped,
        total_input_tokens,
    )
    if dropped:
        log.warning(
            "context_builder dropped %d/%d tail candidates over budget %d "
            "(rank order kept; relevant facts first)",
            dropped,
            len(selected_candidates),
            budget,
        )
    return formatted_context, evidence_manifest, citations_map


def build_strict_grounded_prompt(question: str, formatted_context: str) -> str:
    """Construct strict anti-hallucination grounded prompt for QLoRA student model."""
    prompt = (
        "SYSTEM:\n"
        "You are a grounded document question-answering assistant.\n\n"
        "RULES:\n"
        "1. Use ONLY the supplied evidence below to answer the question.\n"
        "2. Do NOT invent facts or use outside knowledge.\n"
        "3. Preserve all numbers, percentages, precision metrics, and units EXACTLY as written in the evidence.\n"
        "4. If the supplied evidence does NOT contain the information needed to answer, explicitly state: 'The supplied evidence is insufficient to answer this query.'\n"
        "5. Cite the evidence IDs used (e.g. [E1], [E2]) in your answer.\n\n"
        f"SUPPLIED EVIDENCE:\n\n"
        f"{formatted_context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )
    return prompt


class ContextBuilder:
    """Builds budgeted grounded context coordinated with the RAG/QUBO budget."""

    def __init__(
        self,
        max_chunks: int = 5,
        max_graph: int = 5,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        self.max_chunks = max_chunks
        self.max_graph = max_graph
        if max_tokens is None:
            # Coordinate with centralized RAG budget (env RAG_MAX_CONTEXT_TOKENS).
            # Explicit CONTEXT_BUILDER_MAX_TOKENS overrides when set.
            try:
                self.max_tokens = int(get_token_budget_config().effective_context_builder_tokens)
            except Exception:
                self.max_tokens = 3000
        else:
            self.max_tokens = max(100, int(max_tokens))
        # Backward compat: allow max_tokens via kwargs.
        if "max_context_tokens" in kwargs and kwargs["max_context_tokens"] is not None:
            try:
                self.max_tokens = max(100, int(kwargs["max_context_tokens"]))
            except (TypeError, ValueError):
                pass
        log.info(
            "ContextBuilder init max_tokens=%d (max_chunks=%d max_graph=%d)",
            self.max_tokens,
            self.max_chunks,
            self.max_graph,
        )

    def build_context(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        candidates: List[Any] = []
        query: Optional[str] = None

        for arg in args:
            if isinstance(arg, str):
                query = arg
            elif isinstance(arg, list):
                candidates = arg

        if "candidates" in kwargs and kwargs["candidates"] is not None:
            candidates = kwargs["candidates"]
        elif "selected_candidates" in kwargs and kwargs["selected_candidates"] is not None:
            candidates = kwargs["selected_candidates"]

        if "query" in kwargs and kwargs["query"] is not None:
            query = kwargs["query"]

        budget_override = kwargs.get("max_tokens") or kwargs.get("max_context_tokens")
        try:
            budget = int(budget_override) if budget_override is not None else int(self.max_tokens)
        except (TypeError, ValueError):
            budget = int(self.max_tokens)

        converted = []
        for c in candidates:
            if hasattr(c, "model_dump"):
                converted.append(c.model_dump())
            elif hasattr(c, "__dict__") and not isinstance(c, dict):
                converted.append(c.__dict__)
            else:
                converted.append(c)
        ctx_text, manifest, _ = build_grounded_context(converted, max_tokens=budget)
        if query:
            log.debug(
                "ContextBuilder query='%s' candidates=%d manifest=%d budget=%d ctx_tokens=%d",
                query[:60],
                len(converted),
                len(manifest),
                budget,
                estimate_tokens(ctx_text),
            )
        return ctx_text, manifest

    def build_prompt(self, question: str, formatted_context: str) -> str:
        return build_strict_grounded_prompt(question, formatted_context)


__all__ = [
    "build_grounded_context",
    "build_strict_grounded_prompt",
    "ContextBuilder",
]
