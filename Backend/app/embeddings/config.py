"""Phase 6 Embedding & Vector Store Configuration."""
from __future__ import annotations

import os
from pydantic import BaseModel, Field


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (ValueError, AttributeError):
        return default


class EmbeddingConfig(BaseModel):
    """Configurable settings for semantic chunking, embedding generation & vector search.

    Note: ``chunk_size``/``max_chunk_size`` are character budgets for the
    semantic chunker. The embedding model itself is limited to
    ``embedding_max_tokens`` (default 512 for BAAI/bge-small-en-v1.5, minus
    reserved special tokens). Defaults (600/1200 chars ≈ 150/300 tokens)
    fit safely inside 512; the chunker + embedder enforce this in tokens.
    """

    chunk_size: int = 600
    chunk_overlap: int = 100
    min_chunk_size: int = 50
    max_chunk_size: int = 1200
    top_k: int = 5
    batch_size: int = 16
    embedding_provider: str = "sentence_transformers"
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    vector_dimension: int = 384
    cache_embeddings: bool = True
    embedding_max_tokens: int = Field(
        default_factory=lambda: _env_int("EMBEDDING_MAX_TOKENS", 512),
        ge=64,
        le=8192,
        description="Max sequence length of the embedding model including special tokens",
    )
    embedding_reserve_tokens: int = Field(
        default=2, ge=0, le=16, description="Reserved special tokens for embedding inputs"
    )

    model_config = {"extra": "allow"}


default_embedding_config = EmbeddingConfig()


def get_embedding_config() -> EmbeddingConfig:
    return default_embedding_config


__all__ = ["EmbeddingConfig", "default_embedding_config", "get_embedding_config"]
