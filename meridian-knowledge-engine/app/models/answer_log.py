# app/models/answer_log.py
"""AnswerLog model - Audit trail for every query."""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AnswerLog(Base):
    """Answer Logs - Audit trail for every query and answer."""
    __tablename__ = "answer_logs"
    __table_args__ = (
        Index("ix_answer_logs_tenant", "tenant_id"),
        Index("ix_answer_logs_created", "created_at"),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    client_desk: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    as_of_date: Mapped[Optional[date]] = mapped_column(nullable=True)
    route: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # 'computable' | 'lookup' | 'judgment' | 'escalated' | 'refused'
    )
    answer_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    calculator_outputs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    verifier_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    escalated: Mapped[bool] = mapped_column(default=False, nullable=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AnswerLog(id={self.id}, route={self.route}, escalated={self.escalated})>"