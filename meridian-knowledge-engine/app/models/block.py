# app/models/block.py
"""Block model - Parsed structural units: sections, table rows, transcript turns, slides."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, VECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.episode import Episode


class Block(Base):
    """Blocks - Unified structural units from all parsers."""
    __tablename__ = "blocks"
    __table_args__ = (
        Index("ix_blocks_tenant", "tenant_id"),
        Index("ix_blocks_episode", "episode_id"),
        Index("ix_blocks_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}),
        Index("ix_blocks_fts", "content", postgresql_using="gin", postgresql_ops={"content": "tsvector_ops"}),
        Index("ix_blocks_heading", "tenant_id", "heading_path"),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'heading' | 'paragraph' | 'table_row' | 'transcript_turn' | 'slide'
    )
    heading_path: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    heading_level: Mapped[Optional[int]] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    char_start: Mapped[Optional[int]] = mapped_column(nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(VECTOR(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    episode: Mapped["Episode"] = relationship("Episode", back_populates="blocks", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Block(id={self.id}, type={self.block_type}, heading={self.heading_path})>"