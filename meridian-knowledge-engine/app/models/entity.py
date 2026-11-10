# app/models/entity.py
"""Entity model - Domain objects: Client, Vendor, Policy, Invoice, Regulation, Person."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, String, Text, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.fact import Fact


class Entity(Base):
    """Entities - Domain objects in the knowledge graph."""
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_tenant", "tenant_id"),
        Index("ix_entities_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}),
        UniqueConstraint("tenant_id", "entity_type", "canonical_name", name="uq_entities_tenant_type_canonical"),
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
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        # 'client' | 'vendor' | 'policy' | 'invoice' | 'regulation' | 'person'
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    facts_as_subject: Mapped[list["Fact"]] = relationship(
        "Fact",
        foreign_keys="Fact.subject_entity_id",
        back_populates="subject_entity",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Entity(id={self.id}, type={self.entity_type}, name={self.name})>"