# app/store/base.py
"""Base repository class for all database operations."""
from typing import TypeVar, Generic, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, id: UUID) -> Optional[T]:
        """Get by ID."""
        return await self.session.get(self.model, id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all with pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def create(self, obj: T) -> T:
        """Create new object."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: T) -> T:
        """Update existing object."""
        await self.session.merge(obj)
        await self.session.flush()
        return obj

    async def delete(self, id: UUID) -> bool:
        """Delete by ID."""
        obj = await self.get(id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return True
        return False