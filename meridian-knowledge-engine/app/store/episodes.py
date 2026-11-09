# app/store/episodes.py
"""Episode Repository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.store.base import BaseRepository
from app.models.episode import Episode


class EpisodeRepository(BaseRepository[Episode]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Episode)

    async def get_by_source(self, tenant_id: UUID, source_type: str, source_id: str) -> Optional[Episode]:
        stmt = select(Episode).where(
            Episode.tenant_id == tenant_id,
            Episode.source_type == source_type,
            Episode.source_id == source_id,
        )
        return await self.session.scalar(stmt)

    async def get_pending(self, tenant_id: UUID, limit: int = 100) -> List[Episode]:
        stmt = (
            select(Episode)
            .where(Episode.tenant_id == tenant_id, Episode.status == "pending")
            .order_by(Episode.created_at)
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def mark_processing(self, episode_id: UUID) -> None:
        await self.session.execute(
            update(Episode)
            .where(Episode.id == episode_id)
            .values(status="processing")
        )
        await self.session.flush()

    async def mark_completed(self, episode_id: UUID, blocks_count: int = 0, facts_count: int = 0) -> None:
        await self.session.execute(
            update(Episode)
            .where(Episode.id == episode_id)
            .values(status="completed", processed_at=func.now())
        )
        await self.session.flush()

    async def mark_failed(self, episode_id: UUID, error: str) -> None:
        await self.session.execute(
            update(Episode)
            .where(Episode.id == episode_id)
            .values(status="failed", error_message=error)
        )
        await self.session.flush()