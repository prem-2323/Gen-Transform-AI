"""Phase 7 Hybrid Vector + Graph RAG Service Orchestrator.

Orchestrates full Hybrid RAG retrieval & generation pipeline:
Query Analysis -> Dual Retrieval (Vector + Neo4j Graph) -> Fusion & Deduplication ->
Reranking -> Context Validation -> Context & Prompt Building -> Model Generation ->
Citation & Evidence Tracking -> Structured RAG Response.
"""
from __future__ import annotations

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import get_settings
from .citations import CitationTracker
from .context_builder import ContextBuilder
from .fusion import ResultFusion
from .graph_retriever import GraphRetriever
from .prompt_builder import PromptBuilder
from .query_analyzer import QueryAnalyzer
from .reranker import LightweightReranker, RerankerInterface
from .schemas import (
    FusionStrategyEnum,
    GraphEvidence,
    RAGQueryRequest,
    RAGQueryResponse,
    RetrievalMetadata,
    RetrievalResult,
    SourceCitation,
)
from .validator import ContextValidator
from .vector_retriever import VectorRetriever

log = logging.getLogger("gen-transform.rag.service")


class RAGGenerationEngine:
    """Executes model generation using Ollama or grounded fallback engine."""

    def generate_answer(self, prompt: Dict[str, str], candidates: List[RetrievalResult]) -> Tuple[str, float]:
        t_start = time.time()
        settings = get_settings()

        # 1. Try Ollama (e.g. Qwen / Gemma)
        answer = self._call_ollama(prompt, settings)
        if answer:
            latency_ms = round((time.time() - t_start) * 1000, 2)
            return answer, latency_ms

        # 2. Grounded Extractive Fallback Engine
        answer = self._generate_grounded_fallback(candidates)
        latency_ms = round((time.time() - t_start) * 1000, 2)
        return answer, latency_ms

    def _call_ollama(self, prompt: Dict[str, str], settings: Any) -> Optional[str]:
        try:
            import ollama
            try:
                from ..core.token_budgets import estimate_tokens, resolve_output_budget

                _np = int(resolve_output_budget("rag_answer", None))
                _pt = int(estimate_tokens(str(prompt.get("system", "")) + str(prompt.get("user", ""))))
            except Exception:
                _np, _pt = 512, -1
            _model = getattr(settings, "qwen_model", "qwen2.5:7b")
            log.info("rag_generate model=%s prompt_tokens~%d num_predict=%d", _model, _pt, _np)
            client = ollama.Client(host=settings.ollama_base_url, timeout=15)
            resp = client.chat(
                model=_model,
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
                options={"temperature": 0.2, "num_predict": int(_np)},
            )
            return resp["message"]["content"].strip()
        except Exception as exc:
            log.debug("Ollama RAG generation skipped (%s)", exc)
            return None

    def _generate_grounded_fallback(self, candidates: List[Any]) -> str:
        """Deterministic, grounded answer synthesizer built directly from verified evidence."""
        if not candidates:
            return "The retrieved evidence does not contain sufficient information to answer this question."

        def _get(c: Any, field: str, default: Any = "") -> Any:
            if isinstance(c, dict):
                return c.get(field, default)
            return getattr(c, field, default)

        doc_candidates = [c for c in candidates if _get(c, "source_type") == "vector" or _get(c, "source") in ("vector", "pdf", "file")]
        graph_candidates = [c for c in candidates if _get(c, "source_type") == "graph"]
        if not doc_candidates and not graph_candidates:
            doc_candidates = candidates

        lines: List[str] = ["Based on the retrieved vector chunks and knowledge graph evidence:\n"]

        if doc_candidates:
            lines.append("Document Evidence:")
            citation_idx = 1
            for dc in doc_candidates:
                txt = str(_get(dc, "text", "")).strip().replace("\n", " ")
                lines.append(f"- {txt} [{citation_idx}]")
                citation_idx += 1

        if graph_candidates:
            lines.append("\nKnowledge Graph Relationships:")
            for gc in graph_candidates:
                meta = _get(gc, "metadata", {}) or {}
                ev = _get(gc, "evidence", {}) or {}
                src = _get(gc, "source") or meta.get("source") or ev.get("source") or "Entity"
                rel = str(meta.get("relation") or ev.get("relation") or "related_to")
                tgt = meta.get("target") or ev.get("target") or "Target"
                lines.append(f"- {src} {rel.replace('_', ' ').lower()} {tgt}.")

        return "\n".join(lines)


class RAGService:
    """Complete Phase 7 Vector + Graph Hybrid RAG Service."""

    def __init__(
        self,
        query_analyzer: Optional[QueryAnalyzer] = None,
        vector_retriever: Optional[VectorRetriever] = None,
        graph_retriever: Optional[GraphRetriever] = None,
        fusion_engine: Optional[ResultFusion] = None,
        reranker: Optional[RerankerInterface] = None,
        context_builder: Optional[ContextBuilder] = None,
        validator: Optional[ContextValidator] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        citation_tracker: Optional[CitationTracker] = None,
        generator: Optional[RAGGenerationEngine] = None,
    ) -> None:
        self.analyzer = query_analyzer or QueryAnalyzer()
        self.vector_retriever = vector_retriever or VectorRetriever()
        self.graph_retriever = graph_retriever or GraphRetriever()
        self.fusion = fusion_engine or ResultFusion()
        self.reranker = reranker or LightweightReranker()
        self.context_builder = context_builder or ContextBuilder()
        self.validator = validator or ContextValidator()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.citation_tracker = citation_tracker or CitationTracker()
        self.generator = generator or RAGGenerationEngine()

    def query(self, req: RAGQueryRequest) -> RAGQueryResponse:
        """Execute end-to-end Phase 7 Hybrid RAG pipeline."""
        t_pipeline_start = time.time()
        clean_query = (req.query or "").strip()

        # Step 1: Query Analysis
        t_qa_start = time.time()
        analysis = self.analyzer.analyze(clean_query)
        qa_ms = round((time.time() - t_qa_start) * 1000, 2)

        # Step 2: Vector Retrieval
        vector_results, vector_ms = self.vector_retriever.retrieve(
            query=analysis.semantic_query,
            top_k=req.top_k,
            document_id=req.document_id,
            min_score=0.0,
        )

        # Step 3: Graph Retrieval
        graph_results, graph_ms = self.graph_retriever.retrieve(
            analysis=analysis,
            graph_depth=req.graph_depth,
            document_id=req.document_id,
            top_k=req.top_k * 2,
        )

        # Step 4: Result Fusion & Deduplication
        fused_candidates, agreement_detected, potential_conflicts, fusion_ms = self.fusion.fuse_and_deduplicate(
            vector_results=vector_results,
            graph_results=graph_results,
            strategy=req.fusion_strategy,
            vector_weight=req.vector_weight,
            graph_weight=req.graph_weight,
        )

        # Step 5: Candidate Reranking
        if req.rerank and fused_candidates:
            reranked_candidates, rerank_ms = self.reranker.rerank(
                query=clean_query,
                candidates=fused_candidates,
                top_n=req.top_k,
            )
        else:
            reranked_candidates = fused_candidates[: req.top_k]
            rerank_ms = 0.0

        # Step 5.5: Phase 8 Quantum / Hybrid Optimization Layer
        from ..optimization.service import get_optimization_service
        opt_service = get_optimization_service()
        optimized_candidates, opt_metadata = opt_service.optimize_candidates(
            query=clean_query,
            candidates=reranked_candidates,
            max_selected=req.top_k,
        )

        # Step 6: Context Validation (Insufficient Evidence Audit)
        is_sufficient, validation_reason = self.validator.validate(
            candidates=optimized_candidates,
            min_retrieval_score=req.min_retrieval_score,
        )

        if not is_sufficient:
            total_ms = round((time.time() - t_pipeline_start) * 1000, 2)
            log.info("RAG query '%s' returned insufficient evidence (%s)", clean_query[:40], validation_reason)
            return RAGQueryResponse(
                query=clean_query,
                answer=f"The retrieved evidence does not contain sufficient information to answer this question. ({validation_reason})",
                sources=[],
                graph_evidence=[],
                retrieval=RetrievalMetadata(
                    vector_results=len(vector_results),
                    graph_results=len(graph_results),
                    candidate_count=len(fused_candidates),
                    final_context_items=0,
                    query_analysis_ms=qa_ms,
                    vector_ms=vector_ms,
                    graph_ms=graph_ms,
                    fusion_ms=fusion_ms,
                    rerank_ms=rerank_ms,
                    generation_ms=0.0,
                    total_ms=total_ms,
                    agreement_detected=agreement_detected,
                    potential_conflicts=potential_conflicts,
                ),
                insufficient_evidence=True,
                query_analysis=analysis,
                optimization=opt_metadata.model_dump(),
            )

        # Step 7: Context Building
        context_text, selected_candidates = self.context_builder.build_context(
            query=clean_query,
            candidates=optimized_candidates,
        )


        # Step 8: RAG Prompt Construction
        prompt_dict = self.prompt_builder.build_prompt(query=clean_query, context_text=context_text)

        # Step 9: Generation Engine Execution
        answer, generation_ms = self.generator.generate_answer(prompt=prompt_dict, candidates=selected_candidates)

        # Step 10: Citation & Evidence Tracking
        sources, graph_evidence = self.citation_tracker.build_citations(selected_candidates)

        total_ms = round((time.time() - t_pipeline_start) * 1000, 2)

        log.info(
            "Phase 7 RAG query '%s' finished: answer_len=%d, sources=%d, graph_items=%d, total_ms=%s",
            clean_query[:40],
            len(answer),
            len(sources),
            len(graph_evidence),
            total_ms,
        )

        return RAGQueryResponse(
            query=clean_query,
            answer=answer,
            sources=sources,
            graph_evidence=graph_evidence,
            retrieval=RetrievalMetadata(
                vector_results=len(vector_results),
                graph_results=len(graph_results),
                candidate_count=len(fused_candidates),
                final_context_items=len(selected_candidates),
                query_analysis_ms=qa_ms,
                vector_ms=vector_ms,
                graph_ms=graph_ms,
                fusion_ms=fusion_ms,
                rerank_ms=rerank_ms,
                generation_ms=generation_ms,
                total_ms=total_ms,
                agreement_detected=agreement_detected,
                potential_conflicts=potential_conflicts,
            ),
            insufficient_evidence=False,
            query_analysis=analysis,
            optimization=opt_metadata.model_dump(),
        )



_RAG_SERVICE_INSTANCE: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Return singleton instance of RAGService."""
    global _RAG_SERVICE_INSTANCE
    if _RAG_SERVICE_INSTANCE is None:
        _RAG_SERVICE_INSTANCE = RAGService()
    return _RAG_SERVICE_INSTANCE


def reset_rag_service() -> None:
    """Reset singleton instance for testing."""
    global _RAG_SERVICE_INSTANCE
    _RAG_SERVICE_INSTANCE = None


__all__ = ["RAGService", "get_rag_service", "reset_rag_service"]
