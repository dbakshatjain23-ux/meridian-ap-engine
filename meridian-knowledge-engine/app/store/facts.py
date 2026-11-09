# app/store/facts.py
"""Fact Repository - All fact reads/writes for dual-clock temporal graph."""
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.orm import selectinload
from app.store.base import BaseRepository
from app.models.fact import Fact, FactStatus
from app.models.entity import Entity


class FactRepository(BaseRepository[Fact]):
    """Repository for Fact operations with dual-clock temporal queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Fact)

    async def upsert_fact(
        self,
        tenant_id: UUID,
        subject_entity_id: UUID,
        predicate: str,
        object_value: dict,
        object_type: str,
        valid_from: date,
        valid_to: Optional[date],
        source_episode_id: Optional[UUID],
        source_block_ids: List[UUID],
        source_type: str,
        source_version: Optional[str],
        source_status: str,
        authority_rank: int,
        confidence: float = 1.0,
        review_by_date: Optional[date] = None,
        approved_by: Optional[UUID] = None,
    ) -> Fact:
        """
        Atomic upsert: Close old conflicting facts + Insert new fact in single transaction.
        Conflicts = same subject+predicate with overlapping valid time.
        """
        async with self.session.begin():
            # 1. Retract conflicting facts (same subject+predicate, overlapping valid time)
            await self.session.execute(
                update(Fact)
                .where(
                    Fact.tenant_id == tenant_id,
                    Fact.subject_entity_id == subject_entity_id,
                    Fact.predicate == predicate,
                    Fact.retracted_at.is_(None),  # Only currently believed facts
                    # Overlapping valid time: new.valid_from <= old.valid_to AND new.valid_to >= old.valid_from
                    or_(
                        Fact.valid_to.is_(None),  # Old fact has no end date
                        Fact.valid_to >= valid_from,
                    ),
                    Fact.valid_from <= valid_to if valid_to else True,
                )
                .values(retracted_at=func.now(), status=FactStatus.SUPERSEDED)
            )

            # 2. Insert new fact
            new_fact = Fact(
                tenant_id=tenant_id,
                subject_entity_id=subject_entity_id,
                predicate=predicate,
                object_value=object_value,
                object_type=object_type,
                valid_from=valid_from,
                valid_to=valid_to,
                source_episode_id=source_episode_id,
                source_block_ids=source_block_ids,
                source_type=source_type,
                source_version=source_version,
                source_status=source_status,
                authority_rank=authority_rank,
                confidence=confidence,
                review_by_date=review_by_date,
                approved_by=approved_by,
                approved_at=func.now() if approved_by else None,
                status=FactStatus.ACTIVE,
            )
            self.session.add(new_fact)
            await self.session.flush()
            return new_fact

    async def get_current_fact(
        self,
        tenant_id: UUID,
        subject_canonical: str,
        predicate: str,
        as_of_date: Optional[date] = None,
    ) -> Optional[Fact]:
        """Get highest-authority active fact at as_of_date (default: today)."""
        as_of = as_of_date or date.today()
        stmt = (
            select(Fact)
            .join(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.canonical_name == subject_canonical,
                Fact.predicate == predicate,
                Fact.valid_from <= as_of,
                or_(Fact.valid_to.is_(None), Fact.valid_to >= as_of),
                Fact.retracted_at.is_(None),
            )
            .order_by(Fact.authority_rank.asc(), Fact.valid_from.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_fact_at_transaction_time(
        self,
        tenant_id: UUID,
        subject_canonical: str,
        predicate: str,
        as_of_txn: Optional[datetime] = None,
    ) -> Optional[Fact]:
        """Get fact as believed at transaction time (for audit/replay)."""
        as_of = as_of_txn or datetime.utcnow()
        stmt = (
            select(Fact)
            .join(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.canonical_name == subject_canonical,
                Fact.predicate == predicate,
                Fact.recorded_at <= as_of,
                or_(Fact.retracted_at.is_(None), Fact.retracted_at > as_of),
            )
            .order_by(Fact.authority_rank.asc(), Fact.recorded_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_fact_history(
        self,
        tenant_id: UUID,
        subject_canonical: str,
        predicate: str,
    ) -> List[Fact]:
        """Full temporal history for audit/replay."""
        stmt = (
            select(Fact)
            .join(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.canonical_name == subject_canonical,
                Fact.predicate == predicate,
            )
            .order_by(Fact.valid_from.asc(), Fact.recorded_at.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_active_facts_for_subject(
        self,
        tenant_id: UUID,
        subject_entity_id: UUID,
        as_of_date: Optional[date] = None,
    ) -> List[Fact]:
        """Get all active facts for a subject entity."""
        as_of = as_of_date or date.today()
        stmt = (
            select(Fact)
            .where(
                Fact.tenant_id == tenant_id,
                Fact.subject_entity_id == subject_entity_id,
                Fact.valid_from <= as_of,
                or_(Fact.valid_to.is_(None), Fact.valid_to >= as_of),
                Fact.retracted_at.is_(None),
            )
            .order_by(Fact.predicate, Fact.authority_rank.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_facts_by_predicate(
        self,
        tenant_id: UUID,
        predicate: str,
        as_of_date: Optional[date] = None,
    ) -> List[Fact]:
        """Get all active facts for a predicate across all subjects."""
        as_of = as_of_date or date.today()
        stmt = (
            select(Fact)
            .where(
                Fact.tenant_id == tenant_id,
                Fact.predicate == predicate,
                Fact.valid_from <= as_of,
                or_(Fact.valid_to.is_(None), Fact.valid_to >= as_of),
                Fact.retracted_at.is_(None),
            )
            .order_by(Fact.authority_rank.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())