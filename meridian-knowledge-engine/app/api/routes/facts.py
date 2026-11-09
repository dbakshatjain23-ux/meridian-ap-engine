# app/api/routes/facts.py
"""Facts Routes - Graph Query Endpoints."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date, datetime

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth
from app.store.facts import FactRepository
from app.store.entities import EntityRepository
from app.models.user import User

router = APIRouter()


class FactResponse(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    value: dict
    valid_from: str
    valid_to: Optional[str]
    recorded_at: str
    retracted_at: Optional[str]
    authority_rank: int
    source_type: str
    source_version: Optional[str]
    status: str


class FactHistoryResponse(BaseModel):
    fact_id: str
    valid_time_history: List[dict]
    transaction_time_history: List[dict]


@router.get("/facts", response_model=List[FactResponse])
async def query_facts(
    subject: str = Query(..., description="Subject canonical name (e.g., price_tolerance)"),
    predicate: str = Query(..., description="Predicate name (e.g., price_tolerance)"),
    as_of: Optional[str] = Query(None, description="ISO date for valid time query"),
    client_desk: Optional[str] = Query(None, description="Client desk for scope filtering"),
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Query current or historical facts."""
    fact_repo = FactRepository(session)
    entity_repo = EntityRepository(session)

    # Get subject entity
    subject_entity = await entity_repo.get_by_canonical(UUID(tenant_slug), "policy", subject)
    if not subject_entity:
        raise HTTPException(status_code=404, detail=f"Subject '{subject}' not found")

    as_of_date = date.fromisoformat(as_of) if as_of else None

    fact = await fact_repo.get_current_fact(
        UUID(tenant_slug), subject, predicate, as_of_date
    )

    if not fact:
        return []

    return [FactResponse(
        fact_id=str(fact.id),
        subject=subject,
        predicate=fact.predicate,
        value=fact.object_value,
        valid_from=fact.valid_from.isoformat(),
        valid_to=fact.valid_to.isoformat() if fact.valid_to else None,
        recorded_at=fact.recorded_at.isoformat(),
        retracted_at=fact.retracted_at.isoformat() if fact.retracted_at else None,
        authority_rank=fact.authority_rank,
        source_type=fact.source_type,
        source_version=fact.source_version,
        status=fact.status,
    )]


@router.get("/facts/{fact_id}/history", response_model=FactHistoryResponse)
async def get_fact_history(
    fact_id: UUID,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Get full temporal history for a fact (both clocks)."""
    fact_repo = FactRepository(session)
    fact = await fact_repo.get(fact_id)

    if not fact or str(fact.tenant_id) != tenant_slug:
        raise HTTPException(status_code=404, detail="Fact not found")

    history = await fact_repo.get_fact_history(UUID(tenant_slug), fact.subject_entity.canonical_name, fact.predicate)

    valid_time_history = [
        {
            "valid_from": h.valid_from.isoformat(),
            "valid_to": h.valid_to.isoformat() if h.valid_to else None,
            "value": h.object_value,
            "authority_rank": h.authority_rank,
            "source_type": h.source_type,
        }
        for h in history
    ]

    transaction_time_history = [
        {
            "recorded_at": h.recorded_at.isoformat(),
            "retracted_at": h.retracted_at.isoformat() if h.retracted_at else None,
            "value": h.object_value,
            "authority_rank": h.authority_rank,
        }
        for h in history
    ]

    return FactHistoryResponse(
        fact_id=str(fact_id),
        valid_time_history=valid_time_history,
        transaction_time_history=transaction_time_history,
    )