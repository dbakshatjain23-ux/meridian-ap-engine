# app/core/answer/escalation.py
"""Escalation Service - Unanswered -> Owner Review -> Becomes Fact."""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.store.facts import FactRepository
from app.store.entities import EntityRepository
from app.models.fact import Fact
from app.models.entity import Entity
from app.models.escalation import Escalation  # Would need to create


class EscalationService:
    """Manages the escalation loop: Unanswered -> Owner Review -> Approves -> Becomes Fact."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.fact_repo = FactRepository(session)
        self.entity_repo = EntityRepository(session)

    async def create_escalation(
        self,
        tenant_slug: str,
        query_text: str,
        client_desk: str,
        draft_answer: str,
        citations: List[Dict[str, Any]],
        failure_reason: Dict[str, Any],
    ) -> "Escalation":
        """Create escalation ticket for owner review."""
        import uuid as uuid_lib
        from app.models.escalation import Escalation

        escalation = Escalation(
            id=uuid_lib.uuid4(),
            tenant_id=UUID(tenant_slug),
            query_text=query_text,
            client_desk=client_desk,
            draft_answer=draft_answer,
            citations=citations,
            failure_reason=failure_reason,
            status="open",
            created_at=datetime.utcnow(),
        )

        self.session.add(escalation)
        await self.session.flush()

        return escalation

    async def approve_escalation(
        self,
        escalation_id: UUID,
        owner_id: UUID,
        approved_answer: str,
        authority_rank: int = 2,
        review_by_date: Optional[date] = None,
    ) -> Fact:
        """Owner approves escalation -> becomes Fact."""
        escalation = await self.session.get(Escalation, escalation_id)
        if not escalation or escalation.status != "open":
            raise ValueError("Escalation not found or already processed")

        # Determine subject entity from query
        subject_entity = await self._resolve_subject_entity(
            UUID(escalation.tenant_id), escalation.query_text, escalation.client_desk
        )

        # Extract predicate from failure_reason or draft_answer
        predicate = self._extract_predicate(escalation.draft_answer, escalation.failure_reason)

        # Create fact
        fact = await self.fact_repo.upsert_fact(
            tenant_id=escalation.tenant_id,
            subject_entity_id=subject_entity.id,
            predicate=predicate,
            object_value={"answer": approved_answer},
            object_type="json",
            valid_from=date.today(),
            valid_to=None,
            source_episode_id=None,
            source_block_ids=[],
            source_type="owner_approved",
            source_version="escalation",
            source_status="approved",
            authority_rank=authority_rank,
            confidence=0.95,
            review_by_date=review_by_date,
            approved_by=owner_id,
        )

        # Update escalation
        escalation.status = "resolved"
        escalation.resolved_by = owner_id
        escalation.resolved_at = datetime.utcnow()
        escalation.resolved_fact_id = fact.id

        await self.session.commit()

        return fact

    async def _resolve_subject_entity(
        self, tenant_id: UUID, query: str, client_desk: str
    ) -> Entity:
        """Resolve or create subject entity from query."""
        # Simplified: extract key terms and find/create entity
        return await self.entity_repo.get_or_create(
            tenant_id, "policy", "general", "general"
        )

    def _extract_predicate(self, draft_answer: str, failure_reason: Dict[str, Any]) -> str:
        """Extract predicate from draft answer or failure reason."""
        # Simplified: return generic predicate
        return "general_answer"