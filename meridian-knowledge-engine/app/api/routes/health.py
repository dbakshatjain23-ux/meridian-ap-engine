# app/api/routes/health.py
"""Health Check Endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_session
from app.config import get_settings
from app.workers.main import job_processor

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check():
    """Liveness probe - basic health check."""
    return {
        "status": "healthy",
        "service": "meridian-knowledge-engine",
        "version": "0.1.0",
    }


@router.get("/health/ready")
async def readiness_check(session: AsyncSession = Depends(get_session)):
    """Readiness probe - checks DB, Redis, Workers."""
    checks = {}

    # Database
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis (if configured)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"unavailable: {e}"

    # Worker queue depth
    try:
        queue_depth = await job_processor.get_queue_depth() if job_processor else 0
        checks["worker_queue_depth"] = queue_depth
        checks["workers"] = "running" if job_processor else "not_started"
    except Exception as e:
        checks["workers"] = f"error: {e}"

    # Overall status
    all_healthy = all(
        v == "connected" or isinstance(v, int) or v == "running"
        for v in checks.values()
    )

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@router.get("/health/workers")
async def worker_health():
    """Worker-specific health details."""
    if not job_processor:
        return {"status": "not_started"}

    return {
        "status": "running",
        "queue_depth": await job_processor.get_queue_depth(),
        "active_jobs": len(job_processor.active_jobs),
        "completed_jobs": job_processor.stats.completed,
        "failed_jobs": job_processor.stats.failed,
    }