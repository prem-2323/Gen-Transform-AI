"""Phase 8 Quantum / Hybrid Optimization — Problem Formulator.

Converts Phase 7 RetrievalResult candidates into binary decision feature vectors
x_i in {0, 1} and constructs pairwise redundancy matrices for QUBO and classical solvers.
"""
from __future__ import annotations

import re
import logging
from typing import Any, List, Set

from ..rag.schemas import RetrievalResult
from ..core.token_budgets import estimate_tokens, get_token_budget_config
from .config import OptimizationConfig, default_optimization_config
from .schemas import CandidateFeatureVector, OptimizationProblemSchema

log = logging.getLogger("gen-transform.optimization.problem")


class ProblemFormulator:
    """Builds structured OptimizationProblemSchema from raw retrieval candidates."""

    def __init__(self, config: OptimizationConfig = default_optimization_config) -> None:
        self.config = config

    def build_problem(
        self,
        query: str,
        candidates: List[RetrievalResult],
        max_selected: int = 8,
        max_tokens: int = 3000,
    ) -> OptimizationProblemSchema:
        clean_query = (query or "").strip()
        query_words = set(re.findall(r"\b[a-zA-Z0-9\-_]{2,}\b", clean_query.lower()))

        feature_vectors: List[CandidateFeatureVector] = []

        for cand in candidates:
            text = cand.text or ""
            # Centralized token estimate (multilingual-safe); min 10 to avoid zero-cost.
            token_cost = max(10, estimate_tokens(text))

            text_lower = text.lower()
            text_words = set(re.findall(r"\b[a-zA-Z0-9\-_]{2,}\b", text_lower))

            # Feature 1: Relevance Score
            relevance = cand.score if cand.source_type == "vector" else cand.score * 0.75
            if query_words and text_words:
                overlap_ratio = len(query_words.intersection(text_words)) / max(1, len(query_words))
                relevance = max(relevance, overlap_ratio * 0.95)

            # Feature 2: Graph Score
            graph_score = cand.score if cand.source_type == "graph" else 0.0
            if cand.source_type == "graph":
                src = str(cand.metadata.get("source", "")).lower()
                tgt = str(cand.metadata.get("target", "")).lower()
                if (src and src in clean_query.lower()) or (tgt and tgt in clean_query.lower()):
                    graph_score += 0.2
            graph_score = min(1.0, graph_score)

            # Feature 3: Entities Covered
            entities: Set[str] = set()
            for w in text_words:
                if w in query_words and len(w) > 2:
                    entities.add(w)
            if cand.source_type == "graph":
                if cand.metadata.get("source"):
                    entities.add(str(cand.metadata["source"]).lower())
                if cand.metadata.get("target"):
                    entities.add(str(cand.metadata["target"]).lower())

            doc_id = cand.document_id or str(cand.evidence.get("document_id", "doc_default"))

            feature_vectors.append(
                CandidateFeatureVector(
                    candidate_id=cand.source_id,
                    source_type=cand.source_type,
                    document_id=doc_id,
                    text=text,
                    token_cost=token_cost,
                    relevance_score=float(round(relevance, 4)),
                    graph_score=float(round(graph_score, 4)),
                    source_quality=0.9,
                    evidence_quality=float(round(cand.score, 4)),
                    redundancy_score=0.0,
                    entities_covered=sorted(list(entities)),
                    metadata=cand.metadata,
                )
            )

        # Build N x N pairwise redundancy matrix
        n = len(feature_vectors)
        redundancy_matrix: List[List[float]] = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                f_i = feature_vectors[i]
                f_j = feature_vectors[j]
                red = self._calculate_pairwise_redundancy(f_i, f_j)
                redundancy_matrix[i][j] = float(round(red, 4))
                redundancy_matrix[j][i] = float(round(red, 4))

        log.debug("Formulated optimization problem for %d candidates (query='%s')", len(candidates), clean_query[:30])

        return OptimizationProblemSchema(
            query=clean_query,
            candidates=feature_vectors,
            max_selected_candidates=max_selected,
            max_context_tokens=max_tokens,
            pairwise_redundancy_matrix=redundancy_matrix,
        )

    def _calculate_pairwise_redundancy(
        self,
        vec1: CandidateFeatureVector,
        vec2: CandidateFeatureVector,
    ) -> float:
        """Calculate pairwise text redundancy / Jaccard similarity (0.0 to 1.0)."""
        words1 = set(re.findall(r"\b[a-zA-Z0-9\-_]{3,}\b", vec1.text.lower()))
        words2 = set(re.findall(r"\b[a-zA-Z0-9\-_]{3,}\b", vec2.text.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        jaccard = intersection / union if union > 0 else 0.0

        # Identical source and exact chunk match bonus
        if vec1.candidate_id == vec2.candidate_id:
            return 1.0
        if vec1.text.strip() == vec2.text.strip():
            return 1.0

        return min(1.0, jaccard)


__all__ = ["ProblemFormulator"]
