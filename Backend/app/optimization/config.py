"""Phase 6 QUBO & Optimization Configuration."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field

from ..core.token_budgets import RAG_HARD_MAX_TOKENS, get_token_budget_config


def _default_max_context_tokens() -> int:
    try:
        return int(get_token_budget_config().rag_max_context_tokens)
    except Exception:
        return int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "3000"))


class OptimizationConfig(BaseModel):
    """Configuration parameters for Phase 6 QUBO evidence selection optimization."""

    enabled: bool = Field(
        default_factory=lambda: os.getenv("QUBO_ENABLED", "true").lower() == "true",
        description="Master switch for QUBO optimization layer",
    )
    solver: str = Field(
        default_factory=lambda: os.getenv("QUBO_SOLVER", "auto"),
        description="QUBO solver choice: 'auto', 'exact', 'simulated_annealing', or 'quantum'",
    )
    backend: str = Field(
        default_factory=lambda: os.getenv("QUBO_BACKEND", "classical_qubo"),
        description="Backend description: 'classical_qubo' or 'quantum_dwave'",
    )

    # Candidate budget limits
    max_candidates: int = Field(50, ge=1, le=200, description="Max input candidates for QUBO pool")
    default_target_k: int = Field(5, ge=1, le=50, description="Default target selection count K")
    max_context_tokens: int = Field(
        default_factory=_default_max_context_tokens,
        ge=100,
        le=RAG_HARD_MAX_TOKENS,
        description="Max context token budget (centralized: RAG_MAX_CONTEXT_TOKENS, hard cap 16000)",
    )

    # Mathematical QUBO Objective Function Weights
    relevance_weight: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_RELEVANCE_WEIGHT", "1.0")),
        description="Weight alpha for semantic relevance",
    )
    graph_weight: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_GRAPH_WEIGHT", "0.7")),
        description="Weight beta for graph structural score",
    )
    diversity_weight: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_DIVERSITY_WEIGHT", "0.4")),
        description="Weight gamma for evidence quality / diversity",
    )
    redundancy_penalty: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_REDUNDANCY_WEIGHT", "0.8")),
        description="Penalty weight lambda for pairwise redundancy S_ij",
    )
    cardinality_penalty: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_CARDINALITY_PENALTY", "2.0")),
        description="Penalty P for cardinality deviation (sum x_i - K)^2",
    )

    # Simulated Annealing Hyperparameters
    seed: int = Field(
        default_factory=lambda: int(os.getenv("QUBO_SEED", "42")),
        description="Random seed for reproducible simulated annealing",
    )
    annealing_steps: int = Field(
        default_factory=lambda: int(os.getenv("QUBO_ANNEALING_STEPS", "5000")),
        description="Number of MC iterations for simulated annealing",
    )
    initial_temperature: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_INITIAL_TEMPERATURE", "10.0")),
        description="Starting temperature T_0 for simulated annealing",
    )
    final_temperature: float = Field(
        default_factory=lambda: float(os.getenv("QUBO_FINAL_TEMPERATURE", "0.01")),
        description="Ending temperature T_min for simulated annealing",
    )

    # Backward compatibility fields
    evidence_weight: float = Field(0.5, ge=0.0, le=10.0)
    cost_penalty: float = Field(0.05, ge=0.0, le=1.0)
    penalty_token_exceeded: float = Field(10.0)
    penalty_count_exceeded: float = Field(10.0)


default_optimization_config = OptimizationConfig()

__all__ = ["OptimizationConfig", "default_optimization_config"]
