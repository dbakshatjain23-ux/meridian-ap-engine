# app/gateways/embeddings.py
"""Embeddings Gateway - BGE-small + BGE Reranker (Local CPU)."""
import torch
from sentence_transformers import SentenceTransformer
from typing import List, Optional
from app.config import get_settings

settings = get_settings()


class EmbeddingGateway:
    """Local embeddings and reranking - zero API cost."""

    def __init__(self):
        self.embedding_model: Optional[SentenceTransformer] = None
        self.reranker_model: Optional[SentenceTransformer] = None
        self._initialized = False

    def _init_models(self):
        """Lazy initialization of models."""
        if self._initialized:
            return

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # BGE-small-en-v1.5 for embeddings (384 dims)
        self.embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=device,
        )

        # BGE-reranker-base for reranking
        self.reranker_model = SentenceTransformer(
            settings.RERANKER_MODEL,
            device=device,
        )

        self._initialized = True

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        self._init_models()
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=settings.EMBEDDING_BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.embed([text])[0]

    def rerank(self, query: str, passages: List[str], top_k: int = None) -> List[tuple[int, float]]:
        """
        Rerank passages by relevance to query.
        Returns list of (original_index, score) sorted by score descending.
        """
        self._init_models()
        top_k = top_k or settings.RERANKER_TOP_K

        # Create query-passage pairs
        pairs = [[query, passage] for passage in passages]

        # Get relevance scores
        scores = self.reranker_model.predict(
            pairs,
            batch_size=32,
            show_progress_bar=False,
        )

        # Sort by score descending
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores[:top_k]


# Singleton instance
embedding_gateway = EmbeddingGateway()