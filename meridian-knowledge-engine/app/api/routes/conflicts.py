# app/api/routes/conflicts.py
"""Conflicts Routes - Owner Review Dashboard."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth, require_role
from app.store.conflicts import ConflictRepository
from app.store.facts import FactRepository
from app.models.user import User

router = APIRouter()


class ConflictResponse(BaseModel):
    conflict_id: str
    type: str
    severity: str
    fact_1: dict
    fact_2: dict
    detected_at: str
    status: str


class ResolveConflictRequest(BaseModel):
    resolution: str = Field(..., description="fact_1_wins | fact_2_wins | merge | dismiss")
    resolution_notes: str
    resolved_by: str


@router.get("/conflicts", response_model=List[ConflictResponse])
async def list_conflicts(
    status: str = Query("open"),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin", "tax_lead")),
    session: AsyncSession = Depends(get_session),
):
    """List conflicts for owner review."""
    conflict_repo = ConflictRepository(session)
    conflicts = await conflict_repo.get_open(UUID(tenant_slug), severity, limit)

    result = []
    for c in conflicts:
        # Get fact details
        fact1 = await conflict_repo.session.get(c.fact_id_1) if hasattr(conflict_repo, 'session') else None
        fact2 = await conflict_repo.session.get(c.fact_id_2) if hasattr(conflict_repo, 'session') else None

        result.append(ConflictResponse(
            conflict_id=str(c.id),
            type=c.conflict_type,
            severity=c.severity,
            fact_1={
                "fact_id": str(c.fact_id_1),
                "value": fact1.object_value if fact1 else {},
                "source_type": fact1.source_type if fact1 else "",
                "authority_rank": fact1.authority_rank if fact1 else 0,
            },
            fact_2={
                "fact_id": str(c.fact_id_2),
                "value": fact2.object_value if fact2 else {},
                "source_type": fact2.source_type if fact2 else "",
                "authority_rank": fact2.authority_rank if fact2 else 0,
            },
            detected_at=c.created_at.isoformat(),
            status=c.status,
        ))

    return result


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: UUID,
    request: ResolveConflictRequest,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
):
    """Resolve a conflict (owner action)."""
    conflict_repo = ConflictRepository(session)

    resolved = await conflict_repo.resolve(
        conflict_id=conflict_id,
        resolution=request.resolution,
        notes=request.resolution_notes,
        resolved_by=UUID(request.resolved_by),
    )

    if not resolved:
        raise HTTPException(status_code=404, detail="Conflict not found")

    # Apply resolution to facts
    fact_repo = FactRepository(session)

    if request.resolution == "fact_1_wins":
        # Retract fact_2
        await fact_repo.session.execute(
            update(Fact).where(Fact.id == resolved.fact_id_2).values(
                retracted_at=func.now(), status="superseded"
            )
        )
    elif request.resolution == "fact_2_wins":
        # Retract fact_1
        await fact_repo.session.execute(
            update(Fact).where(Fact.id == resolved.fact_id_1).values(
                retracted_at=func.now(), status="superseded"
            )
        )
    elif request.resolution == "dismiss":
        # Mark both as reviewed, no change
        pass

    await session.commit()

    return {"status": "resolved", "conflict_id": str(conflict_id), "resolution": request.resolution}