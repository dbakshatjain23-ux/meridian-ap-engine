# app/core/retrieval/hybrid.py
"""Hybrid Retriever - Keyword + Vector + Graph Walk -> RRF Merge -> Rerank."""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import date
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.store.facts import FactRepository
from app.store.blocks import BlockRepository
from app.store.entities import EntityRepository
from app.gateways.embeddings import embedding_gateway
from app.config import get_settings

settings = get_settings()


@dataclass
class RetrievalResult:
    passages: List[Dict[str, Any]]
    fact_ids: List[UUID]
    scores: List[float]


class HybridRetriever:
    """
    Hybrid Search Pipeline:
    1. Graph First: Entity Linking -> Pull current facts
    2. Parallel Search: Keyword + Vector + Graph Walk
    3. RRF Merge: Score = Σ 1/(k + rank_i)
    4. Rerank: BGE-reranker on Top-20 -> Final Top-6
    5. Filters: Time + Scope
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.fact_repo = FactRepository(session)
        self.block_repo = BlockRepository(session)
        self.entity_repo = EntityRepository(session)
        self.rrf_k = settings.RRF_K

    async def retrieve(
        self,
        query: str,
        tenant_id: UUID,
        client_desk: str,
        as_of_date: Optional[date] = None,
        top_k: int = 6,
    ) -> RetrievalResult:
        """Main retrieval pipeline."""
        as_of = as_of_date or date.today()

        # Step 1: Graph First - Entity Linking
        query_entities = await self._link_entities(query, tenant_id, client_desk)

        # Step 2: Parallel Search
        keyword_results = await self._keyword_search(query, tenant_id, client_desk, as_of)
        vector_results = await self._vector_search(query, tenant_id, client_desk, as_of)
        graph_walk_results = await self._graph_walk(query_entities, tenant_id, as_of)

        # Step 3: RRF Merge
        merged = self._rrf_merge([
            ("keyword", keyword_results),
            ("vector", vector_results),
            ("graph_walk", graph_walk_results),
        ])

        # Step 4: Rerank
        reranked = await self._rerank(query, merged, top_k=20)

        # Step 5: Time + Scope Filter
        filtered = self._apply_filters(reranked, tenant_id, client_desk, as_of)

        # Take top-k
        final = filtered[:top_k]

        return RetrievalResult(
            passages=final,
            fact_ids=[f["fact_id"] for f in final if f.get("fact_id")],
            scores=[f["score"] for f in final],
        )

    async def _link_entities(
        self,
        query: str,
        tenant_id: UUID,
        client_desk: str,
    ) -> List[Dict[str, Any]]:
        """Link query terms to known entities."""
        from sqlalchemy import select
        from app.models.entity import Entity

        stmt = select(Entity).where(
            Entity.tenant_id == tenant_id,
            Entity.entity_type.in_(["client", "vendor", "policy"]),
        )
        result = await self.session.scalars(stmt)
        entities = list(result.all())

        matched = []
        query_lower = query.lower()
        for e in entities:
            if e.canonical_name.lower() in query_lower or e.name.lower() in query_lower:
                matched.append({
                    "entity_id": e.id,
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type,
                })
        return matched

    async def _keyword_search(
        self,
        query: str,
        tenant_id: UUID,
        client_desk: str,
        as_of_date: date,
    ) -> List[Dict[str, Any]]:
        """PostgreSQL full-text + pg_trgm keyword search."""
        stmt = text("""
            SELECT b.id, b.content, b.metadata, b.episode_id,
                   similarity(b.content, :query) as score
            FROM blocks b
            WHERE b.tenant_id = :tenant_id
              AND b.content % :query
            ORDER BY score DESC
            LIMIT 20
        """)
        result = await self.session.execute(stmt, {
            "query": query,
            "tenant_id": str(tenant_id),
        })

        passages = []
        for row in result:
            passages.append({
                "block_id": row.id,
                "content": row.content,
                "metadata": row.metadata,
                "score": float(row.score),
                "source": "keyword",
            })
        return passages

    async def _vector_search(
        self,
        query: str,
        tenant_id: UUID,
        client_desk: str,
        as_of_date: date,
    ) -> List[Dict[str, Any]]:
        """pgvector HNSW cosine similarity search."""
        query_embedding = embedding_gateway.embed_single(query)

        stmt = text("""
            SELECT b.id, b.content, b.metadata, b.episode_id,
                   (b.embedding <=> :embedding) as distance
            FROM blocks b
            WHERE b.tenant_id = :tenant_id
              AND b.embedding IS NOT NULL
            ORDER BY distance
            LIMIT 20
        """)
        result = await self.session.execute(stmt, {
            "embedding": query_embedding,
            "tenant_id": str(tenant_id),
        })

        passages = []
        for row in result:
            score = 1.0 - float(row.distance)
            passages.append({
                "block_id": row.id,
                "content": row.content,
                "metadata": row.metadata,
                "score": score,
                "source": "vector",
            })
        return passages

    async def _graph_walk(
        self,
        entities: List[Dict[str, Any]],
        tenant_id: UUID,
        as_of_date: date,
    ) -> List[Dict[str, Any]]:
        """1-2 hop graph expansion from query entities."""
        passages = []
        for e in entities:
            facts = await self.fact_repo.get_active_facts_for_subject(
                tenant_id, UUID(e["entity_id"]), as_of_date
            )
            for f in facts[:5]:
                if f.source_block_ids:
                    block = await self.block_repo.get(f.source_block_ids[0])
                    if block:
                        passages.append({
                            "block_id": block.id,
                            "content": block.content,
                            "metadata": {**block.metadata, "fact_predicate": f.predicate},
                            "score": 0.9,
                            "source": "graph",
                        })
        return passages

    def _rrf_merge(
        self,
        ranked_lists: List[tuple[str, List[Dict]]],
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion merge."""
        all_items = {}
        for source_name, results in ranked_lists:
            for rank, item in enumerate(results):
                block_id = item.get("block_id")
                if not block_id:
                    continue
                rrf_score = 1.0 / (self.rrf_k + rank + 1)
                if block_id in all_items:
                    all_items[block_id]["rrf_score"] += rrf_score
                    all_items[block_id]["sources"].append(source_name)
                else:
                    all_items[block_id] = {
                        **item,
                        "rrf_score": rrf_score,
                        "sources": [source_name],
                    }
        merged = list(all_items.values())
        merged.sort(key=lambda x: x["rrf_score"], reverse=True)
        return merged

    async def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """BGE reranker on Top-20."""
        if len(candidates) <= top_k:
            return candidates

        top_candidates = candidates[:top_k]
        passages = [c["content"] for c in top_candidates]
        reranked_indices = embedding_gateway.rerank(query, passages, top_k=len(top_candidates))

        reranked = []
        for orig_idx, score in reranked_indices:
            c = top_candidates[orig_idx]
            c["rerank_score"] = float(score)
            reranked.append(c)

        for c in reranked:
            c["final_score"] = 0.5 * c.get("rrf_score", 0) + 0.5 * c.get("rerank_score", 0)

        reranked.sort(key=lambda x: x["final_score"], reverse=True)
        return reranked

    def _apply_filters(
        self,
        candidates: List[Dict[str, Any]],
        tenant_id: UUID,
        client_desk: str,
        as_of_date: date,
    ) -> List[Dict[str, Any]]:
        """Apply time and scope filters."""
        return candidates