# app/api/routes/tacit.py
"""Tacit Knowledge Capture Routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth, require_role
from app.store.facts import FactRepository
from app.store.entities import EntityRepository
from app.models.user import User

router = APIRouter()


class TacitCaptureRequest(BaseModel):
    vendor_id: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    habit_description: str = Field(..., min_length=1)
    action_to_take: str = Field(..., min_length=1)
    rule_predicate: str = Field(..., min_length=1)
    source_timestamp: str = Field(..., min_length=1)
    captured_by: str = Field(..., min_length=1)
    approver_id: str = Field(..., min_length=1)
    review_by_date: str = Field(..., min_length=1)


class TacitCaptureResponse(BaseModel):
    fact_id: str
    status: str
    authority_rank: int
    review_by_date: str
    message: str


class TacitListResponse(BaseModel):
    fact_id: str
    vendor_id: str
    topic: str
    habit_description: str
    action_to_take: str
    rule_predicate: str
    status: str
    authority_rank: int
    review_by_date: str
    approved_by: Optional[str]
    approved_at: Optional[str]


@router.post("/tacit/capture", response_model=TacitCaptureResponse)
async def capture_tacit(
    request: TacitCaptureRequest,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin", "senior")),
    session: AsyncSession = Depends(get_session),
):
    """
    Capture a new tacit knowledge card (expert practice).
    Requires owner/admin/senior role.
    """
    fact_repo = FactRepository(session)
    entity_repo = EntityRepository(session)

    # Get or create vendor entity
    vendor_entity = await entity_repo.get_by_canonical(
        UUID(tenant_slug), "vendor", request.vendor_id.lower()
    )
    if not vendor_entity:
        vendor_entity = await entity_repo.get_or_create(
            UUID(tenant_slug), "vendor", request.vendor_id, request.vendor_id.lower()
        )

    # Parse review_by_date
    review_by = date.fromisoformat(request.review_by_date)

    # Create fact
    fact = await fact_repo.upsert_fact(
        tenant_id=UUID(tenant_slug),
        subject_entity_id=vendor_entity.id,
        predicate=request.rule_predicate,
        object_value={
            "topic": request.topic,
            "habit_description": request.habit_description,
            "action_to_take": request.action_to_take,
        },
        object_type="json",
        valid_from=date.today(),
        valid_to=None,
        source_episode_id=None,
        source_block_ids=[],
        source_type="expert_interview",
        source_version="tacit_capture",
        source_status="approved",
        authority_rank=3,  # Tacit = rank 3
        confidence=0.9,
        review_by_date=review_by,
        approved_by=UUID(request.approver_id),
    )

    return TacitCaptureResponse(
        fact_id=str(fact.id),
        status=fact.status,
        authority_rank=fact.authority_rank,
        review_by_date=fact.review_by_date.isoformat(),
        message="Practice card created and approved. Will appear side-by-side with rule.",
    )


@router.get("/tacit/list", response_model=List[TacitListResponse])
async def list_tacit(
    vendor_id: Optional[str] = None,
    status: Optional[str] = None,
    expiring_within_days: Optional[int] = None,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """List tacit knowledge cards (owner view)."""
    fact_repo = FactRepository(session)

    # Get vendor entity if specified
    vendor_entity_id = None
    if vendor_id:
        entity_repo = EntityRepository(session)
        vendor_entity = await entity_repo.get_by_canonical(UUID(tenant_slug), "vendor", vendor_id.lower())
        if vendor_entity:
            vendor_entity_id = vendor_entity.id

    # Query facts with source_type=expert_interview
    from sqlalchemy import select, and_, or_
    from app.models.fact import Fact
    from app.models.entity import Entity

    stmt = (
        select(Fact)
        .join(Entity, Fact.subject_entity_id == Entity.id)
        .where(
            Entity.tenant_id == UUID(tenant_slug),
            Fact.source_type == "expert_interview",
        )
    )

    if vendor_entity_id:
        stmt = stmt.where(Fact.subject_entity_id == vendor_entity_id)

    if status:
        stmt = stmt.where(Fact.status == status)

    if expiring_within_days:
        from datetime import date, timedelta
        expiry_cutoff = date.today() + timedelta(days=expiring_within_days)
        stmt = stmt.where(
            Fact.review_by_date.is_not(None),
            Fact.review_by_date <= expiry_cutoff,
        )

    result = await session.scalars(stmt)
    facts = list(result.all())

    return [
        TacitListResponse(
            fact_id=str(f.id),
            vendor_id=f.subject_entity_id,  # Would need to resolve to actual vendor ID
            topic=f.object_value.get("topic", ""),
            habit_description=f.object_value.get("habit_description", ""),
            action_to_take=f.object_value.get("action_to_take", ""),
            rule_predicate=f.predicate,
            status=f.status,
            authority_rank=f.authority_rank,
            review_by_date=f.review_by_date.isoformat() if f.review_by_date else "",
            approved_by=str(f.approved_by) if f.approved_by else None,
            approved_at=f.approved_at.isoformat() if f.approved_at else None,
        )
        for f in facts
    ]