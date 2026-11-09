# app/models/fact.py
"""Fact model - Core knowledge: Dual-clock temporal edges."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    DateTime, Date, String, Text, ForeignKey, Index, ARRAY, func, Integer, Float, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.episode import Episode
    from app.models.conflict import Conflict


class FactStatus(str):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    CONFLICT = "conflict"
    PENDING_REVIEW = "pending_review"


class Fact(Base):
    """Facts - Dual-clock temporal knowledge edges."""
    __tablename__ = "facts"
    __table_args__ = (
        Index("ix_facts_tenant", "tenant_id"),
        Index("ix_facts_subject_predicate", "subject_entity_id", "predicate"),
        Index("ix_facts_valid_time", "valid_from", "valid_to"),
        Index("ix_facts_txn_time", "recorded_at", "retracted_at"),
        Index("ix_facts_authority", "authority_rank"),
        Index("ix_facts_status", "status", postgresql_where="status IN ('active', 'conflict', 'pending_review')"),
        # GiST Range Index for Valid Time Queries
        Index(
            "ix_facts_valid_range",
            "tenant_id",
            "valid_from",
            "valid_to",
            postgresql_using="gist",
        ),
        # GiST Range Index for Transaction Time Queries
        Index(
            "ix_facts_txn_range",
            "tenant_id",
            "recorded_at",
            "retracted_at",
            postgresql_using="gist",
        ),
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
    subject_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predicate: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    object_value = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # 'json' | 'string' | 'number' | 'date' | 'boolean'
    )

    # VALID TIME (When true in the world)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # NULL = currently true

    # TRANSACTION TIME (When system learned/retracted)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    retracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # NULL = currently believed

    # SOURCE & AUTHORITY
    source_episode_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.episodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_block_ids = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'client_memo' | 'sop' | 'desk_instruction' | 'faq' | 'expert_interview' | 'meeting' | 'email' | 'chat'
    )
    source_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'current' | 'superseded' | 'draft' | 'unreviewed'
    )
    authority_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # Lower = Higher Authority

    # CONFIDENCE & GOVERNANCE
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=FactStatus.ACTIVE,
        nullable=False,
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_by_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    subject_entity: Mapped["Entity"] = relationship("Entity", back_populates="facts_as_subject", lazy="selectin")
    source_episode: Mapped[Optional["Episode"]] = relationship("Episode", back_populates="facts", lazy="selectin")
    conflicts_as_fact1: Mapped["list[Conflict]"] = relationship(
        "Conflict",
        foreign_keys="Conflict.fact_id_1",
        back_populates="fact_1",
        lazy="selectin",
    )
    conflicts_as_fact2: Mapped["list[Conflict]"] = relationship(
        "Conflict",
        foreign_keys="Conflict.fact_id_2",
        back_populates="fact_2",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Fact(id={self.id}, predicate={self.predicate}, authority={self.authority_rank}, status={self.status})>"