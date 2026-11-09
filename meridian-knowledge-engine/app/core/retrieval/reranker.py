# app/core/retrieval/reranker.py
"""Reranker wrapper - already implemented in embeddings gateway."""
from app.gateways.embeddings import embedding_gateway

# Re-export for clarity
Reranker = embedding_gateway.__class__
reranker = embedding_gateway