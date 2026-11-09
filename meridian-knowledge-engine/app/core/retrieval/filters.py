# app/core/retrieval/filters.py
"""Time and Scope Filters for Retrieval."""
from typing import List, Dict, Any
from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models.fact import Fact
from app.models.entity import Entity


class TimeScopeFilter:
    """Filters retrieval results by valid time and client scope."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def filter_facts_by_time_and_scope(
        self,
        fact_ids: List[UUID],
        tenant_id: UUID,
        client_desk: str,
        as_of_date: date,
    ) -> List[Fact]:
        """Filter facts by valid time (as_of_date) and client scope."""
        stmt = (
            select(Fact)
            .join(Entity, Fact.subject_entity_id == Entity.id)
            .where(
                Fact.id.in_(fact_ids),
                Fact.tenant_id == tenant_id,
                Fact.valid_from <= as_of_date,
                or_(Fact.valid_to.is_(None), Fact.valid_to >= as_of_date),
                Fact.retracted_at.is_(None),
                # Scope: General rules + client-specific rules
                or_(
                    Entity.canonical_name.in_(["general", client_desk.lower().replace(" ", "_")]),
                    Entity.metadata.op("->>")("scope") == "ALL",
                ),
            )
            .order_by(Fact.authority_rank.asc(), Fact.valid_from.desc())
        )

        result = await self.session.scalars(stmt)
        return list(result.all())

    @staticmethod
    def filter_passages_by_scope(
        passages: List[Dict[str, Any]],
        client_desk: str,
    ) -> List[Dict[str, Any]]:
        """Filter passages by client desk scope."""
        filtered = []
        for p in passages:
            metadata = p.get("metadata", {})
            scope = metadata.get("scope", "ALL")
            desk = metadata.get("client_desk", "ALL")

            if scope == "ALL" or desk == "ALL" or desk == client_desk:
                filtered.append(p)

        return filtered