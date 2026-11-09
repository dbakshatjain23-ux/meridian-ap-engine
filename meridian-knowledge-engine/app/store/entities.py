# app/store/entities.py
"""Entity Repository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.store.base import BaseRepository
from app.models.entity import Entity


class EntityRepository(BaseRepository[Entity]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Entity)

    async def get_by_canonical(self, tenant_id: UUID, entity_type: str, canonical_name: str) -> Optional[Entity]:
        stmt = select(Entity).where(
            Entity.tenant_id == tenant_id,
            Entity.entity_type == entity_type,
            Entity.canonical_name == canonical_name,
        )
        return await self.session.scalar(stmt)

    async def get_or_create(
        self,
        tenant_id: UUID,
        entity_type: str,
        name: str,
        canonical_name: str,
        metadata: Optional[dict] = None,
    ) -> Entity:
        existing = await self.get_by_canonical(tenant_id, entity_type, canonical_name)
        if existing:
            return existing
        entity = Entity(
            tenant_id=tenant_id,
            entity_type=entity_type,
            name=name,
            canonical_name=canonical_name,
            metadata=metadata or {},
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_type(self, tenant_id: UUID, entity_type: str) -> List[Entity]:
        stmt = select(Entity).where(Entity.tenant_id == tenant_id, Entity.entity_type == entity_type)
        result = await self.session.scalars(stmt)
        return list(result.all())