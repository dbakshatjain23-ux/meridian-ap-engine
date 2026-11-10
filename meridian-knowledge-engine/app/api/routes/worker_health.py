# app/api/routes/worker_health.py
"""Worker Health Check Routes - Monitoring and observability for background workers."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth
from app.models.job import Job
from app.models.user import User

router = APIRouter(prefix="/workers", tags=["workers"])


class WorkerHealthResponse(BaseModel):
    worker_id: str
    status: str  # "healthy", "unhealthy", "unknown"
    last_heartbeat: Optional[datetime]
    jobs_processed_1h: int
    jobs_failed_1h: int
    avg_processing_time_ms: Optional[float]
    queue_depth: int


class QueueStatsResponse(BaseModel):
    pending: int
    running: int
    retrying: int
    failed: int
    completed_1h: int
    by_type: Dict[str, int]


@router.get("/health", response_model=List[WorkerHealthResponse])
async def get_workers_health(
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Get health status of all workers.
    
    Returns health metrics for each worker based on job processing patterns.
    """
    # Get distinct worker IDs from recent jobs
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    result = await session.execute(
        text("""
            SELECT DISTINCT worker_id
            FROM jobs
            WHERE tenant_id = :tenant_id
              AND started_at > :since
              AND worker_id IS NOT NULL
        """),
        {"tenant_id": tenant_slug, "since": one_hour_ago}
    )
    
    worker_ids = [row[0] for row in result.fetchall()]
    
    health_data = []
    for worker_id in worker_ids:
        # Get stats for this worker
        stats = await session.execute(
            text("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000) as avg_time,
                    MAX(completed_at) as last_heartbeat
                FROM jobs
                WHERE worker_id = :worker_id
                  AND tenant_id = :tenant_id
                  AND started_at > :since
            """),
            {"worker_id": worker_id, "tenant_id": tenant_slug, "since": one_hour_ago}
        )
        
        row = stats.fetchone()
        
        # Get current queue depth
        queue_depth = await session.scalar(
            select(func.count(Job.id)).where(
                Job.tenant_id == tenant_slug,
                Job.status.in_(["queued", "running", "retrying"])
            )
        ) or 0
        
        health_data.append(WorkerHealthResponse(
            worker_id=worker_id,
            status="healthy" if row.last_heartbeat and (datetime.utcnow() - row.last_heartbeat).seconds < 300 else "unhealthy",
            last_heartbeat=row.last_heartbeat,
            jobs_processed_1h=row.completed or 0,
            jobs_failed_1h=row.failed or 0,
            avg_processing_time_ms=row.avg_time,
            queue_depth=queue_depth,
        ))
    
    return health_data


@router.get("/queue/stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Get current queue statistics.
    """
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    # Overall counts
    pending = await session.scalar(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_slug,
            Job.status == "queued"
        )
    ) or 0
    
    running = await session.scalar(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_slug,
            Job.status == "running"
        )
    ) or 0
    
    retrying = await session.scalar(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_slug,
            Job.status == "retrying"
        )
    ) or 0
    
    failed = await session.scalar(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_slug,
            Job.status == "failed"
        )
    ) or 0
    
    completed_1h = await session.scalar(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_slug,
            Job.status == "completed",
            Job.completed_at > one_hour_ago
        )
    ) or 0
    
    # By job type
    type_stats = await session.execute(
        text("""
            SELECT job_type, COUNT(*) as count
            FROM jobs
            WHERE tenant_id = :tenant_id
              AND status IN ('queued', 'running', 'retrying')
            GROUP BY job_type
        """),
        {"tenant_id": tenant_slug}
    )
    
    by_type = {row[0]: row[1] for row in type_stats.fetchall()}
    
    return QueueStatsResponse(
        pending=pending,
        running=running,
        retrying=retrying,
        failed=failed,
        completed_1h=completed_1h,
        by_type=by_type,
    )


@router.post("/queue/retry-failed")
async def retry_failed_jobs(
    job_type: Optional[str] = None,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Retry failed jobs (move them back to queued status).
    """
    query = (
        Job.__table__.update()
        .where(Job.tenant_id == tenant_slug)
        .where(Job.status == "failed")
        .values(status="queued", error_message=None, scheduled_for=func.now())
    )
    
    if job_type:
        query = query.where(Job.job_type == job_type)
    
    result = await session.execute(query)
    await session.commit()
    
    return {"retried_count": result.rowcount}


@router.delete("/queue/clear-failed")
async def clear_failed_jobs(
    job_type: Optional[str] = None,
    older_than_hours: int = 24,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete old failed jobs from the queue.
    """
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    
    query = (
        Job.__table__.delete()
        .where(Job.tenant_id == tenant_slug)
        .where(Job.status == "failed")
        .where(Job.completed_at < cutoff)
    )
    
    if job_type:
        query = query.where(Job.job_type == job_type)
    
    result = await session.execute(query)
    await session.commit()
    
    return {"deleted_count": result.rowcount}


# Pydantic models need to be imported
from pydantic import BaseModel