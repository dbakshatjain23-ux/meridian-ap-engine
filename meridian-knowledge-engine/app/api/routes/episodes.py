# app/api/routes/episodes.py
"""Episode Ingestion Routes - Document upload and live capture webhooks."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import hashlib

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth
from app.store.episodes import EpisodeRepository
from app.models.user import User

router = APIRouter()


class EpisodeStatusResponse(BaseModel):
    episode_id: str
    status: str
    blocks_extracted: int = 0
    facts_created: int = 0
    conflicts_detected: int = 0
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None


class UploadResponse(BaseModel):
    episode_id: str
    job_id: str
    status: str
    message: str


# ============================================================
# Document/File Upload
# ============================================================

@router.post("/episodes/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form("document"),
    metadata: str = Form("{}"),
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a document for ingestion.
    Supported: PDF, Word, Excel, PowerPoint, Text, Email.
    """
    import json

    # Read file content
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # Check deduplication
    episode_repo = EpisodeRepository(session)
    existing = await session.execute(
        select(Episode).where(
            Episode.tenant_id == UUID(tenant_slug),
            Episode.content_hash == content_hash,
        )
    )
    if existing.scalar():
        raise HTTPException(status_code=409, detail="Document already ingested (same content hash)")

    # Create episode
    import json as json_lib
    meta = json_lib.loads(metadata) if metadata else {}
    meta["filename"] = file.filename
    meta["content_type"] = file.content_type
    meta["uploaded_by"] = str(user.id)

    episode = Episode(
        tenant_id=UUID(tenant_slug),
        source_type=source_type,
        source_id=file.filename,
        source_metadata=meta,
        raw_content=content.decode("utf-8", errors="ignore") if file.content_type and "text" in file.content_type else None,
        content_hash=content_hash,
        status="pending",
    )
    session.add(episode)
    await session.flush()

    # Queue ingestion job
    from app.models.job import Job
    job = Job(
        tenant_id=UUID(tenant_slug),
        job_type="ingest",
        payload={"episode_id": str(episode.id)},
        status="queued",
    )
    session.add(job)
    await session.flush()

    return UploadResponse(
        episode_id=str(episode.id),
        job_id=str(job.id),
        status="queued",
        message="Ingestion started. Check job status for completion.",
    )


@router.get("/episodes/{episode_id}/status", response_model=EpisodeStatusResponse)
async def get_episode_status(
    episode_id: UUID,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Get ingestion status for an episode."""
    episode_repo = EpisodeRepository(session)
    episode = await episode_repo.get(episode_id)

    if not episode or str(episode.tenant_id) != tenant_slug:
        raise HTTPException(status_code=404, detail="Episode not found")

    # Count blocks and facts
    from sqlalchemy import select, func
    from app.models.block import Block
    from app.models.fact import Fact

    blocks_count = await session.scalar(
        select(func.count(Block.id)).where(Block.episode_id == episode_id)
    ) or 0

    facts_count = await session.scalar(
        select(func.count(Fact.id)).where(Fact.source_episode_id == episode_id)
    ) or 0

    conflicts_count = await session.scalar(
        select(func.count(Conflict.id)).where(
            Conflict.fact_id_1.in_(
                select(Fact.id).where(Fact.source_episode_id == episode_id)
            )
        )
    ) or 0

    processing_time = None
    if episode.processed_at and episode.created_at:
        processing_time = int((episode.processed_at - episode.created_at).total_seconds() * 1000)

    return EpisodeStatusResponse(
        episode_id=str(episode.id),
        status=episode.status,
        blocks_extracted=blocks_count,
        facts_created=facts_count,
        conflicts_detected=conflicts_count,
        processing_time_ms=processing_time,
        error_message=episode.error_message,
    )


# ============================================================
# Live Capture Webhooks
# ============================================================

class EmailWebhookRequest(BaseModel):
    message_id: str
    from_: str = Field(..., alias="from")
    to: List[str]
    subject: str
    body: str
    received_at: str
    attachments: List[dict] = []


@router.post("/episodes/email/webhook")
async def email_webhook(
    request: EmailWebhookRequest,
    x_webhook_signature: Optional[str] = Header(None),
    tenant_slug: str = Depends(get_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Email webhook for real-time ingestion (Microsoft Graph / IMAP)."""
    # Verify webhook signature (implement HMAC verification)
    # ...

    # Create episode
    episode = Episode(
        tenant_id=UUID(tenant_slug),
        source_type="email",
        source_id=request.message_id,
        source_metadata={
            "from": request.from_,
            "to": request.to,
            "subject": request.subject,
            "received_at": request.received_at,
            "attachments": request.attachments,
        },
        raw_content=request.body,
        content_hash=hashlib.sha256(request.body.encode()).hexdigest(),
        status="pending",
    )
    session.add(episode)
    await session.flush()

    # Queue ingestion job
    from app.models.job import Job
    job = Job(
        tenant_id=UUID(tenant_slug),
        job_type="ingest",
        payload={"episode_id": str(episode.id)},
        status="queued",
    )
    session.add(job)
    await session.flush()

    return {"status": "queued", "episode_id": str(episode.id), "job_id": str(job.id)}


class TeamsWebhookRequest(BaseModel):
    message_id: str
    channel_id: str
    from_: dict = Field(..., alias="from")
    body: str
    timestamp: str
    thread_id: Optional[str] = None
    reactions: List[dict] = []


@router.post("/episodes/teams/webhook")
async def teams_webhook(
    request: TeamsWebhookRequest,
    x_webhook_signature: Optional[str] = Header(None),
    tenant_slug: str = Depends(get_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Teams message webhook for real-time ingestion."""
    episode = Episode(
        tenant_id=UUID(tenant_slug),
        source_type="chat",
        source_id=request.message_id,
        source_metadata={
            "channel_id": request.channel_id,
            "from": request.from_,
            "timestamp": request.timestamp,
            "thread_id": request.thread_id,
            "reactions": request.reactions,
        },
        raw_content=request.body,
        content_hash=hashlib.sha256(request.body.encode()).hexdigest(),
        status="pending",
    )
    session.add(episode)
    await session.flush()

    from app.models.job import Job
    job = Job(
        tenant_id=UUID(tenant_slug),
        job_type="ingest",
        payload={"episode_id": str(episode.id)},
        status="queued",
    )
    session.add(job)
    await session.flush()

    return {"status": "queued", "episode_id": str(episode.id), "job_id": str(job.id)}


class MeetingStartRequest(BaseModel):
    platform: str  # teams | zoom | meet
    meeting_url: str
    record: bool = True
    transcribe: bool = True
    diarize: bool = True


@router.post("/episodes/meeting/start")
async def start_meeting(
    request: MeetingStartRequest,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Trigger meeting bot to join a call."""
    # This would integrate with meeting bot service
    # For now, create episode and return meeting ID
    import uuid as uuid_lib
    meeting_id = str(uuid_lib.uuid4())

    episode = Episode(
        tenant_id=UUID(tenant_slug),
        source_type="meeting",
        source_id=meeting_id,
        source_metadata={
            "platform": request.platform,
            "meeting_url": request.meeting_url,
            "started_by": str(user.id),
        },
        content_hash=hashlib.sha256(meeting_id.encode()).hexdigest(),
        status="pending",
    )
    session.add(episode)
    await session.flush()

    return {
        "meeting_id": meeting_id,
        "bot_id": f"bot_{meeting_id[:8]}",
        "status": "joining",
        "websocket_url": f"wss://api.meridian-engine.com/v1/episodes/meeting/{meeting_id}/stream",
    }