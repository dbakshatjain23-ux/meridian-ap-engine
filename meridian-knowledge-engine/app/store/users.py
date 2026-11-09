# app/store/users.py
"""User Repository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.store.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, tenant_id: UUID, email: str) -> Optional[User]:
        stmt = select(User).where(User.tenant_id == tenant_id, User.email == email)
        return await self.session.scalar(stmt)

    async def get_by_role(self, tenant_id: UUID, role: str) -> List[User]:
        stmt = select(User).where(User.tenant_id == tenant_id, User.role == role, User.is_active == True)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_owners(self, tenant_id: UUID) -> List[User]:
        return await self.get_by_role(tenant_id, "owner")