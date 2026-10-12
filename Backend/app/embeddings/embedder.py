"""Phase 3 Real Embedding Models & Provider Abstraction.

Supports production SentenceTransformers (BAAI/bge-small-en-v1.5 or all-MiniLM-L6-v2),
device detection (CUDA/CPU), batching, L2 normalization, and explicit error reporting.
Also retains DeterministicEmbeddingModel strictly for offline unit tests.
"""
from __future__ import annotations

import math
import hashlib
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from ..core.config import get_settings
from .metadata import compute_content_hash

log = logging.getLogger("gen-transform.embeddings.embedder")

_EMBEDDING_CACHE: Dict[str, List[float]] = {}


class EmbeddingModelInterface(ABC):
    """Abstract interface contract for embedding models."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension (e.g. 384 or 768 or 1536)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Model identifier name."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings into float vectors."""
        pass


class SentenceTransformerEmbeddingModel(EmbeddingModelInterface):
    """Production Real Embedding Model backed by SentenceTransformers (e.g. BAAI/bge-small-en-v1.5).

    Supports automatic CUDA/CPU detection, L2 vector normalization, batch processing,
    and explicit error reporting with NO silent fallback to deterministic hash vectors.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        normalize: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        self._model_name = model_name or getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
        self._normalize = normalize if normalize is not None else getattr(settings, "embedding_normalize", True)

        pref_device = (device or getattr(settings, "embedding_device", "auto")).lower().strip()
        import torch

        self._cuda_available = torch.cuda.is_available()

        if pref_device == "cuda":
            if self._cuda_available:
                self._device = "cuda"
            else:
                log.warning("CUDA requested for embeddings but PyTorch reports CUDA unavailable; falling back to CPU.")
                self._device = "cpu"
        elif pref_device == "auto":
            self._device = "cuda" if self._cuda_available else "cpu"
        else:
            self._device = "cpu"

        log.info(
            "Initializing SentenceTransformer model '%s' on device '%s' (CUDA available: %s, normalize: %s)",
            self._model_name,
            self._device,
            self._cuda_available,
            self._normalize,
        )

        try:
            from sentence_transformers import SentenceTransformer
            import os

            # Disable noisy HuggingFace warnings
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

            # Prefer cached local files first for instant startup (0s network delay)
            try:
                self._model = SentenceTransformer(
                    self._model_name,
                    device=self._device,
                    local_files_only=True,
                )
            except Exception:
                self._model = SentenceTransformer(self._model_name, device=self._device)

            get_dim = getattr(self._model, "get_embedding_dimension", getattr(self._model, "get_sentence_embedding_dimension", None))
            self._dim = get_dim() if get_dim else 384
        except Exception as exc:
            log.error("Failed to load SentenceTransformer model '%s': %s", self._model_name, exc)
            raise RuntimeError(f"Could not load SentenceTransformer model '{self._model_name}': {exc}") from exc

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return f"sentence-transformers:{self._model_name}"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def device(self) -> str:
        return self._device

    @property
    def cuda_available(self) -> bool:
        return self._cuda_available

    @property
    def normalize(self) -> bool:
        return self._normalize

    def embed_text(self, text: str) -> List[float]:
        clean = (text or "").strip()
        if not clean:
            return [0.0] * self._dim

        # Defensive: never send more than the model's sequence length.
        try:
            from ..core.token_budgets import ensure_embedding_budget

            settings = get_settings()
            max_tok = int(getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5") and 512 or 512)
            try:
                max_tok = int(os.getenv("EMBEDDING_MAX_TOKENS", "512"))
            except (TypeError, ValueError):
                max_tok = 512
            clean, info = ensure_embedding_budget(clean, max_tokens=max_tok)
            if info.get("truncated"):
                log.warning(
                    "embed_text truncated original=%s kept=%s max=%s",
                    info.get("original_tokens"),
                    info.get("kept_tokens"),
                    max_tok,
                )
        except Exception:
            pass

        vec = self._model.encode(
            clean,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [float(x) for x in vec]

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return self.embed_batch(texts, batch_size=batch_size)

    def embed_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        if not texts:
            return []

        settings = get_settings()
        b_size = batch_size or getattr(settings, "embedding_batch_size", 16)

        cleaned_texts = [t if (t and t.strip()) else " " for t in texts]
        # Defensive per-item clamp to the embedding sequence length.
        try:
            from ..core.token_budgets import ensure_embedding_budget as _eeb

            try:
                _max = int(os.getenv("EMBEDDING_MAX_TOKENS", "512"))
            except (TypeError, ValueError):
                _max = 512
            clamped: List[str] = []
            for _t in cleaned_texts:
                try:
                    _c, _info = _eeb(_t, max_tokens=_max)
                    if _info.get("truncated"):
                        log.warning(
                            "embed_batch item truncated original=%s kept=%s",
                            _info.get("original_tokens"),
                            _info.get("kept_tokens"),
                        )
                    clamped.append(_c)
                except Exception:
                    clamped.append(_t)
            cleaned_texts = clamped
        except Exception:
            pass

        vecs = self._model.encode(
            cleaned_texts,
            batch_size=b_size,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        res: List[List[float]] = []
        for i, raw in enumerate(vecs):
            if not texts[i] or not texts[i].strip():
                res.append([0.0] * self._dim)
            else:
                res.append([float(x) for x in raw])
        return res


class DeterministicEmbeddingModel(EmbeddingModelInterface):
    """Deterministic 384-dimensional vector generator used strictly for unit tests."""

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension
        self._name = f"deterministic-{dimension}d"

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return self._name

    def _hash_vector(self, text: str) -> List[float]:
        ch_hash = compute_content_hash(text)

        if ch_hash in _EMBEDDING_CACHE:
            return _EMBEDDING_CACHE[ch_hash]

        raw = [0.0] * self._dim
        words = [w.strip().lower() for w in text.split() if w.strip()]

        for w in words:
            w_bytes = w.encode("utf-8")
            h = int(hashlib.md5(w_bytes).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 4) & 1) == 1 else -1.0
            raw[idx] += sign * (1.0 + math.log(1 + len(w)))

        for i in range(len(text) - 2):
            gram = text[i : i + 3].lower().encode("utf-8")
            h = int(hashlib.sha256(gram).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 2) & 1) == 1 else -1.0
            raw[idx] += 0.3 * sign

        norm = math.sqrt(sum(v * v for v in raw))
        if norm > 1e-9:
            normalized = [round(v / norm, 6) for v in raw]
        else:
            normalized = [0.0] * self._dim

        _EMBEDDING_CACHE[ch_hash] = normalized
        return normalized

    def embed_text(self, text: str) -> List[float]:
        return self._hash_vector(text)

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return self.embed_batch(texts)

    def embed_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class OllamaEmbeddingModel(EmbeddingModelInterface):
    """Local Ollama embedding provider."""

    def __init__(self, model_name: str = "nomic-embed-text", dimension: int = 768) -> None:
        self._model = model_name
        self._dim = dimension
        self._name = f"ollama:{model_name}"

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return self._name

    def embed_text(self, text: str) -> List[float]:
        import ollama

        settings = get_settings()
        client = ollama.Client(host=settings.ollama_base_url)
        resp = client.embeddings(model=self._model, prompt=text)
        vec = resp.get("embedding") if isinstance(resp, dict) else getattr(resp, "embedding", None)
        if vec and isinstance(vec, list):
            return vec
        raise RuntimeError(f"Ollama returned invalid embedding vector for model {self._model}")

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return self.embed_batch(texts)

    def embed_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


_DEFAULT_EMBEDDER: Optional[EmbeddingModelInterface] = None


def set_default_embedder(embedder: Optional[EmbeddingModelInterface]) -> None:
    """Set global active default embedding model."""
    global _DEFAULT_EMBEDDER
    _DEFAULT_EMBEDDER = embedder


def get_embedder(provider: Optional[str] = None) -> EmbeddingModelInterface:
    """Factory resolving active embedding model provider.

    Default production path uses SentenceTransformerEmbeddingModel.
    Raises explicit RuntimeError on initialization failure with NO silent fallback.
    """
    global _DEFAULT_EMBEDDER
    if _DEFAULT_EMBEDDER is not None and provider is None:
        return _DEFAULT_EMBEDDER

    settings = get_settings()
    p = (provider or getattr(settings, "embedding_provider", "sentence_transformers")).lower().strip()

    if p in ("sentence_transformers", "sentence-transformers", "real"):
        inst = SentenceTransformerEmbeddingModel()
        if provider is None:
            _DEFAULT_EMBEDDER = inst
        return inst

    if p in ("deterministic", "mock"):
        inst = DeterministicEmbeddingModel(dimension=getattr(settings, "vector_dimension", 384))
        if provider is None:
            _DEFAULT_EMBEDDER = inst
        return inst

    if p.startswith("ollama"):
        return OllamaEmbeddingModel()

    try:
        inst = SentenceTransformerEmbeddingModel()
        if provider is None:
            _DEFAULT_EMBEDDER = inst
        return inst
    except Exception as exc:
        log.error("Failed to initialize SentenceTransformers embedder: %s", exc)
        raise RuntimeError(f"Embedding provider initialization failed for '{p}': {exc}") from exc


def clear_embedding_cache() -> None:
    """Clear local content-hash embedding cache."""
    _EMBEDDING_CACHE.clear()


__all__ = [
    "EmbeddingModelInterface",
    "SentenceTransformerEmbeddingModel",
    "DeterministicEmbeddingModel",
    "OllamaEmbeddingModel",
    "get_embedder",
    "set_default_embedder",
    "clear_embedding_cache",
]
