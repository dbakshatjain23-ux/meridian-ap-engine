# app/core/ingestion/graph_writer.py
"""Atomic Graph Writer - Close Old + Open New in Single Transaction."""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, func, select

from app.models.fact import Fact, FactStatus
from app.models.entity import Entity
from app.store.facts import FactRepository
from app.store.entities import EntityRepository


class GraphWriter:
    """Handles atomic graph writes: Close Old + Open New."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.fact_repo = FactRepository(session)
        self.entity_repo = EntityRepository(session)

    async def upsert_facts(
        self,
        tenant_id: UUID,
        new_facts: List[Dict[str, Any]],
    ) -> List[Fact]:
        """
        Atomic upsert: For each new fact, retract conflicting existing facts
        and insert new fact in single transaction.
        """
        created_facts = []

        async with self.session.begin():
            for nf in new_facts:
                # 1. Get or create subject entity
                subject_entity = await self._get_or_create_subject_entity(
                    tenant_id, nf
                )

                # 2. Retract conflicting facts
                await self._retract_conflicting_facts(
                    tenant_id=tenant_id,
                    subject_entity_id=subject_entity.id,
                    predicate=nf["predicate"],
                    valid_from=nf["valid_from"],
                    valid_to=nf.get("valid_to"),
                )

                # 3. Insert new fact
                new_fact = Fact(
                    tenant_id=tenant_id,
                    subject_entity_id=subject_entity.id,
                    predicate=nf["predicate"],
                    object_value=nf["object_value"],
                    object_type=nf["object_type"],
                    valid_from=nf["valid_from"],
                    valid_to=nf.get("valid_to"),
                    source_episode_id=nf.get("source_episode_id"),
                    source_block_ids=nf.get("source_block_ids", []),
                    source_type=nf["source_type"],
                    source_version=nf.get("source_version"),
                    source_status=nf.get("source_status", "current"),
                    authority_rank=nf["authority_rank"],
                    confidence=nf.get("confidence", 1.0),
                    review_by_date=nf.get("review_by_date"),
                    approved_by=nf.get("approved_by"),
                    approved_at=func.now() if nf.get("approved_by") else None,
                    status=FactStatus.ACTIVE,
                )
                self.session.add(new_fact)
                await self.session.flush()
                created_facts.append(new_fact)

        return created_facts

    async def _get_or_create_subject_entity(
        self,
        tenant_id: UUID,
        new_fact: Dict[str, Any],
    ) -> Entity:
        """Get or create subject entity for fact."""
        subject_id = new_fact.get("subject_entity_id")
        if subject_id:
            entity = await self.session.get(Entity, subject_id)
            if entity and entity.tenant_id == tenant_id:
                return entity

        # Create from fact data
        subject_type = new_fact.get("subject_type", "policy")
        subject_name = new_fact.get("subject_name", "Unknown")
        canonical = new_fact.get("subject_canonical", subject_name.lower().replace(" ", "_"))

        return await self.entity_repo.get_or_create(
            tenant_id=tenant_id,
            entity_type=subject_type,
            name=subject_name,
            canonical_name=canonical,
            metadata=new_fact.get("subject_metadata", {}),
        )

    async def _retract_conflicting_facts(
        self,
        tenant_id: UUID,
        subject_entity_id: UUID,
        predicate: str,
        valid_from: date,
        valid_to: Optional[date],
    ) -> int:
        """Retract (close) conflicting facts - same subject+predicate, overlapping valid time."""
        conditions = [
            Fact.tenant_id == tenant_id,
            Fact.subject_entity_id == subject_entity_id,
            Fact.predicate == predicate,
            Fact.retracted_at.is_(None),  # Only currently believed facts
        ]

        # Overlapping valid time: new.valid_from <= old.valid_to AND new.valid_to >= old.valid_from
        if valid_to:
            conditions.append(Fact.valid_to >= valid_from)
            conditions.append(Fact.valid_from <= valid_to)
        else:
            # New fact has no end date - overlaps with any existing that hasn't ended
            conditions.append(Fact.valid_to.is_(None) | (Fact.valid_to >= valid_from))

        result = await self.session.execute(
            update(Fact)
            .where(*conditions)
            .values(retracted_at=func.now(), status=FactStatus.SUPERSEDED)
        )

        return result.rowcount