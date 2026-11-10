# app/models/escalation.py
"""Escalation model - Unanswered questions escalated to owner review."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Escalation(Base):
    """Escalation tickets - Unanswered questions escalated to owner review."""
    __tablename__ = "escalations"
    __table_args__ = (
        Index("ix_escalations_tenant", "tenant_id"),
        Index("ix_escalations_status", "status"),
        Index("ix_escalations_client_desk", "client_desk"),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    client_desk: Mapped[str] = mapped_column(String(100), nullable=False)
    draft_answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    failure_reason: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        # 'open' | 'resolved' | 'dismissed'
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_fact_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Escalation(id={self.id}, status={self.status}, client_desk={self.client_desk})>"