"""Additional indexes for performance.

Revision ID: 002
Revises: 001
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additional composite indexes for common query patterns
    op.create_index(
        'ix_facts_tenant_predicate_valid',
        'facts',
        ['tenant_id', 'predicate', 'valid_from', 'valid_to'],
        schema='public'
    )

    op.create_index(
        'ix_blocks_tenant_type_content',
        'blocks',
        ['tenant_id', 'block_type'],
        schema='public',
        postgresql_where=sa.text("block_type IN ('heading', 'paragraph')")
    )

    op.create_index(
        'ix_episodes_tenant_created',
        'episodes',
        ['tenant_id', 'created_at'],
        schema='public'
    )


def downgrade() -> None:
    op.drop_index('ix_facts_tenant_predicate_valid', 'facts', schema='public')
    op.drop_index('ix_blocks_tenant_type_content', 'blocks', schema='public')
    op.drop_index('ix_episodes_tenant_created', 'episodes', schema='public')