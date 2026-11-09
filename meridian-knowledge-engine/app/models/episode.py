# app/models/episode.py
"""Episode model - Raw inputs: documents, emails, meetings, chats, uploads."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.block import Block
    from app.models.fact import Fact


class Episode(Base):
    """Episodes - Raw input sources (documents, emails, meetings, chats, uploads)."""
    __tablename__ = "episodes"
    __table_args__ = (
        Index("ix_episodes_tenant", "tenant_id"),
        Index("ix_episodes_source", "source_type", "source_id"),
        Index("ix_episodes_status", "status", postgresql_where=__table_args__[2] if False else None),  # placeholder
        UniqueConstraint("tenant_id", "content_hash", name="uq_episodes_dedup"),
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
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'document' | 'email' | 'meeting' | 'chat' | 'upload'
    )
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_metadata: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        # 'pending' | 'processing' | 'completed' | 'failed'
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    blocks: Mapped[list["Block"]] = relationship(
        "Block",
        back_populates="episode",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    facts: Mapped[list["Fact"]] = relationship(
        "Fact",
        back_populates="source_episode",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Episode(id={self.id}, type={self.source_type}, status={self.status})>"


# Add the missing index for status
from sqlalchemy import DDL, event

@event.listens_for(Episode.__table__, "after_create")
def create_status_index(*args, **kwargs):
    """Create partial index for pending/processing episodes."""
    pass  # Created via migration