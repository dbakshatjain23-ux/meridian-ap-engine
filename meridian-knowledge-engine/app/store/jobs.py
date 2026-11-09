# app/store/jobs.py
"""Job Repository - Postgres SKIP LOCKED Queue."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from app.store.base import BaseRepository
from app.models.job import Job


class JobRepository(BaseRepository[Job]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Job)

    async def claim_next_job(self, worker_id: str, job_types: Optional[List[str]] = None) -> Optional[Job]:
        """
        Atomically claim the next queued job using SELECT FOR UPDATE SKIP LOCKED.
        Returns the claimed job or None if queue empty.
        """
        stmt = (
            select(Job)
            .where(
                Job.status == "queued",
                Job.scheduled_for <= func.now(),
            )
        )
        if job_types:
            stmt = stmt.where(Job.job_type.in_(job_types))

        stmt = stmt.order_by(Job.scheduled_for).limit(1)

        # Use raw SQL for SKIP LOCKED
        raw_sql = text("""
            SELECT id, tenant_id, job_type, payload, status, attempts, max_attempts,
                   error_message, scheduled_for, started_at, completed_at, created_at
            FROM jobs
            WHERE status = 'queued'
              AND scheduled_for <= NOW()
              AND (:job_types IS NULL OR job_type = ANY(:job_types))
            ORDER BY scheduled_for
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        """)
        result = await self.session.execute(raw_sql, {"job_types": job_types})
        row = result.first()
        if not row:
            return None

        # Update status to running
        job_id = row.id
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status="running", started_at=func.now(), attempts=Job.attempts + 1)
        )
        await self.session.flush()

        return await self.get(job_id)

    async def complete_job(self, job_id: UUID, result: Optional[dict] = None) -> None:
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status="completed", completed_at=func.now())
        )
        await self.session.flush()

    async def fail_job(self, job_id: UUID, error: str) -> None:
        job = await self.get(job_id)
        if not job:
            return
        if job.attempts >= job.max_attempts:
            await self.session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="failed", error_message=error, completed_at=func.now())
            )
        else:
            await self.session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="retrying", error_message=error, scheduled_for=func.now() + timedelta(seconds=30 * job.attempts))
            )
        await self.session.flush()

    async def get_pending_count(self, tenant_id: UUID) -> int:
        stmt = select(func.count(Job.id)).where(Job.tenant_id == tenant_id, Job.status.in_(["queued", "running", "retrying"]))
        return await self.session.scalar(stmt) or 0