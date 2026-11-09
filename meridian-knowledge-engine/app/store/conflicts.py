# app/store/conflicts.py
"""Conflict Repository."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.store.base import BaseRepository
from app.models.conflict import Conflict


class ConflictRepository(BaseRepository[Conflict]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Conflict)

    async def get_open(self, tenant_id: UUID, severity: Optional[str] = None, limit: int = 50) -> List[Conflict]:
        stmt = select(Conflict).where(Conflict.tenant_id == tenant_id, Conflict.status == "open")
        if severity:
            stmt = stmt.where(Conflict.severity == severity)
        stmt = stmt.order_by(Conflict.created_at.desc()).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def resolve(
        self,
        conflict_id: UUID,
        resolution: str,
        notes: str,
        resolved_by: UUID,
    ) -> Optional[Conflict]:
        conflict = await self.get(conflict_id)
        if not conflict:
            return None
        conflict.status = "resolved"
        conflict.resolution_notes = notes
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.utcnow()
        await self.session.flush()
        return conflict