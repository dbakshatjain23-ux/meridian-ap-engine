# app/store/blocks.py
"""Block Repository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.store.base import BaseRepository
from app.models.block import Block


class BlockRepository(BaseRepository[Block]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Block)

    async def get_by_episode(self, episode_id: UUID) -> List[Block]:
        stmt = select(Block).where(Block.episode_id == episode_id).order_by(Block.char_start)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def bulk_create(self, blocks: List[Block]) -> List[Block]:
        self.session.add_all(blocks)
        await self.session.flush()
        return blocks