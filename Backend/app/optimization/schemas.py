"""Phase 8 Quantum / Hybrid Optimization Schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateFeatureVector(BaseModel):
    """Extracted numeric & domain features for a single retrieval candidate (vector or graph)."""

    candidate_id: str
    source_type: str = Field("vector", description="'vector' or 'graph'")

    document_id: str = Field("doc_default")
    text: str
    token_cost: int = Field(50, ge=1)
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)
    graph_score: float = Field(0.0, ge=0.0, le=1.0)
    source_quality: float = Field(0.9, ge=0.0, le=1.0)
    evidence_quality: float = Field(0.9, ge=0.0, le=1.0)
    redundancy_score: float = Field(0.0, ge=0.0, le=1.0)
    entities_covered: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OptimizationProblemSchema(BaseModel):
    """Formulated binary decision optimization problem."""

    query: str
    candidates: List[CandidateFeatureVector]
    max_selected_candidates: int = 8
    max_context_tokens: int = 3000
    pairwise_redundancy_matrix: List[List[float]] = Field(default_factory=list)


class OptimizationResultSchema(BaseModel):
    """Result of optimization execution from classical, quantum, or hybrid solver."""

    selected_candidate_ids: List[str] = Field(default_factory=list)
    objective_value: float = Field(0.0, description="Calculated objective score of selected subset")
    solver_used: str = Field(..., description="'classical', 'quantum', 'mock_quantum', or 'hybrid'")
    latency_ms: float = Field(0.0, description="Optimization execution time in milliseconds")
    constraints_satisfied: bool = Field(True, description="Whether all hard constraints are satisfied")
    candidates_before: int = Field(0)
    candidates_after: int = Field(0)
    qubo_matrix_size: Optional[int] = Field(None, description="Size of N x N QUBO matrix if formulated")
    fallback_triggered: bool = Field(False, description="True if quantum solver fell back to classical")


class OptimizationMetadata(BaseModel):
    """Metadata included in final RAG response for tracing optimization layer state."""

    enabled: bool = True
    backend: str = "hybrid"
    candidates_before: int = 0
    candidates_after: int = 0
    objective_value: float = 0.0
    constraints_satisfied: bool = True
    latency_ms: float = 0.0
    solver_used: str = "classical"
    fallback_triggered: bool = False


class OptimizationSelectRequest(BaseModel):
    """Request payload for standalone POST /api/optimization/select endpoint."""

    query: str = Field(..., min_length=1, description="Target search query")
    candidates: List[Dict[str, Any]] = Field(..., description="List of retrieval candidate dictionaries")
    backend: str = Field("hybrid", description="'classical', 'quantum', or 'hybrid'")
    max_selected: int = Field(8, ge=1, le=50)
    # Centralized budget: default RAG_MAX_CONTEXT_TOKENS=3000, hard cap 16000
    # (see app.core.token_budgets). Range preserved for API compatibility.
    max_tokens: int = Field(3000, ge=100, le=16000)


class OptimizationSelectResponse(BaseModel):
    """Response payload for standalone POST /api/optimization/select endpoint."""

    query: str
    selected_candidates: List[Dict[str, Any]]
    optimization: OptimizationMetadata


__all__ = [
    "CandidateFeatureVector",
    "OptimizationProblemSchema",
    "OptimizationResultSchema",
    "OptimizationMetadata",
    "OptimizationSelectRequest",
    "OptimizationSelectResponse",
]
