# app/store/answers.py
"""AnswerLog Repository."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.store.base import BaseRepository
from app.models.answer_log import AnswerLog


class AnswerLogRepository(BaseRepository[AnswerLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AnswerLog)

    async def log_answer(
        self,
        tenant_id: UUID,
        query_text: str,
        client_desk: Optional[str],
        as_of_date: Optional[date],
        route: str,
        answer_markdown: Optional[str],
        citations: Optional[dict],
        calculator_outputs: Optional[dict],
        verifier_result: Optional[dict],
        escalated: bool,
        escalation_reason: Optional[str],
        response_time_ms: int,
    ) -> AnswerLog:
        log = AnswerLog(
            tenant_id=tenant_id,
            query_text=query_text,
            client_desk=client_desk,
            as_of_date=as_of_date,
            route=route,
            answer_markdown=answer_markdown,
            citations=citations,
            calculator_outputs=calculator_outputs,
            verifier_result=verifier_result,
            escalated=escalated,
            escalation_reason=escalation_reason,
            response_time_ms=response_time_ms,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_recent(self, tenant_id: UUID, limit: int = 100) -> List[AnswerLog]:
        stmt = (
            select(AnswerLog)
            .where(AnswerLog.tenant_id == tenant_id)
            .order_by(AnswerLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_stats(self, tenant_id: UUID, since: Optional[datetime] = None) -> dict:
        stmt = select(
            func.count(AnswerLog.id).label("total"),
            func.avg(AnswerLog.response_time_ms).label("avg_response_ms"),
            func.sum(func.cast(AnswerLog.escalated, Integer)).label("escalated_count"),
        ).where(AnswerLog.tenant_id == tenant_id)
        if since:
            stmt = stmt.where(AnswerLog.created_at >= since)
        result = await self.session.execute(stmt)
        row = result.first()
        return {
            "total": row.total or 0,
            "avg_response_ms": float(row.avg_response_ms) if row.avg_response_ms else 0,
            "escalated_count": row.escalated_count or 0,
        }