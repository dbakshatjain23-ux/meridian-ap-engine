# app/api/routes/sop_sync.py
"""SOP Sync Routes - Change Detection, Redline Generation, Push to SharePoint/Git."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth, require_role
from app.store.facts import FactRepository
from app.models.user import User

router = APIRouter()


class PendingChangeResponse(BaseModel):
    fact_id: str
    action: str  # update | insert | delete
    predicate: str
    old_value: Optional[dict]
    new_value: Optional[dict]
    source: str
    detected_at: str


class GenerateRedlineRequest(BaseModel):
    target_document: str  # e.g., "SOP_v4.0.docx"
    changes: List[str]  # fact_ids
    output_format: str = "docx"  # docx | pdf | html


class PushSyncRequest(BaseModel):
    target: str  # sharepoint | github | gitlab
    document_id: str
    redline_id: str
    commit_message: str
    notify: List[str] = []


class AcknowledgementResponse(BaseModel):
    sync_id: str
    acknowledged: List[dict]
    pending: List[dict]


@router.get("/sop/sync/pending", response_model=List[PendingChangeResponse])
async def get_pending_sync_changes(
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
):
    """Get pending SOP sync changes from recent fact updates."""
    fact_repo = FactRepository(session)

    # Find recently created/updated facts that affect SOPs
    from sqlalchemy import select
    from app.models.fact import Fact
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(hours=24)
    stmt = (
        select(Fact)
        .where(
            Fact.tenant_id == UUID(tenant_slug),
            Fact.recorded_at >= cutoff,
            Fact.status == "active",
            Fact.predicate.in_(["price_tolerance", "tds_section", "tds_rate", "msme_cap", "e_invoice_threshold", "approval_limit"]),
        )
        .order_by(Fact.recorded_at.desc())
    )

    result = await session.scalars(stmt)
    facts = list(result.all())

    return [
        PendingChangeResponse(
            fact_id=str(f.id),
            action="update" if f.retracted_at else "insert",
            predicate=f.predicate,
            old_value=None,  # Would need to query previous version
            new_value=f.object_value,
            source=f.source_type,
            detected_at=f.recorded_at.isoformat(),
        )
        for f in facts
    ]


@router.post("/sop/sync/generate-redline")
async def generate_redline(
    request: GenerateRedlineRequest,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
):
    """Generate redline document with tracked changes."""
    # This would use python-docx to create tracked changes
    # For now, return placeholder
    return {
        "redline_id": f"redline_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "document": request.target_document,
        "changes_applied": request.changes,
        "output_format": request.output_format,
        "download_url": f"/v1/sop/sync/redline/redline_{{id}}/download",
        "message": "Redline generation queued",
    }


@router.post("/sop/sync/push")
async def push_sync(
    request: PushSyncRequest,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
):
    """Push redline to SharePoint/Git and notify stakeholders."""
    # Queue sync job
    from app.models.job import Job
    job = Job(
        tenant_id=UUID(tenant_slug),
        job_type="sop_sync",
        payload={
            "target": request.target,
            "document_id": request.document_id,
            "redline_id": request.redline_id,
            "commit_message": request.commit_message,
            "notify": request.notify,
        },
        status="queued",
    )
    session.add(job)
    await session.flush()

    return {
        "sync_id": str(job.id),
        "status": "queued",
        "message": "SOP sync job queued for processing",
    }


@router.get("/sop/sync/acknowledgements", response_model=AcknowledgementResponse)
async def get_acknowledgements(
    sync_id: str,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_role("owner", "admin")),
    session: AsyncSession = Depends(get_session),
):
    """Track acknowledgements for SOP changes."""
    # Would query sync tracking table
    return AcknowledgementResponse(
        sync_id=sync_id,
        acknowledged=[],
        pending=[],
    )