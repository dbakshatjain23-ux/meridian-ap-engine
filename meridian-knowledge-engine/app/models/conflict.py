# app/models/conflict.py
"""Conflict model - Detected contradictions for owner review."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.fact import Fact


class Conflict(Base):
    """Conflicts - Detected contradictions between facts."""
    __tablename__ = "conflicts"
    __table_args__ = (
        Index("ix_conflicts_tenant", "tenant_id"),
        Index("ix_conflicts_status", "status", postgresql_where="status = 'open'"),
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
    fact_id_1: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facts.id", ondelete="CASCADE"),
        nullable=False,
    )
    fact_id_2: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("facts.id", ondelete="CASCADE"),
        nullable=False,
    )
    conflict_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'direct_contradiction' | 'parameter_drift' | 'scope_overlap' | 'authority_clash'
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # 'critical' | 'high' | 'medium' | 'low'
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        # 'open' | 'resolved' | 'dismissed'
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    fact_1: Mapped["Fact"] = relationship(
        "Fact",
        foreign_keys=[fact_id_1],
        back_populates="conflicts_as_fact1",
        lazy="selectin",
    )
    fact_2: Mapped["Fact"] = relationship(
        "Fact",
        foreign_keys=[fact_id_2],
        back_populates="conflicts_as_fact2",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Conflict(id={self.id}, type={self.conflict_type}, severity={self.severity}, status={self.status})>"