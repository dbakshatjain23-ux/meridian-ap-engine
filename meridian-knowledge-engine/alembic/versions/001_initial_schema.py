"""Initial dual-clock temporal knowledge graph schema.

Revision ID: 001
Revises: 
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist;')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # tenants
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), unique=True, nullable=False),
        sa.Column('settings', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True, schema='public')

    # episodes
    op.create_table(
        'episodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('source_id', sa.Text(), nullable=False),
        sa.Column('source_metadata', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        schema='public'
    )
    op.create_index('ix_episodes_tenant', 'episodes', ['tenant_id'], schema='public')
    op.create_index('ix_episodes_source', 'episodes', ['source_type', 'source_id'], schema='public')
    op.create_index('ix_episodes_status', 'episodes', ['status'], schema='public', postgresql_where=sa.text("status IN ('pending', 'processing')"))
    op.create_unique_constraint('uq_episodes_dedup', 'episodes', ['tenant_id', 'content_hash'], schema='public')

    # blocks
    op.create_table(
        'blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('episode_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('episodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('block_type', sa.Text(), nullable=False),
        sa.Column('heading_path', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('heading_level', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('embedding', postgresql.VECTOR(384), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index('ix_blocks_tenant', 'blocks', ['tenant_id'], schema='public')
    op.create_index('ix_blocks_episode', 'blocks', ['episode_id'], schema='public')
    op.create_index('ix_blocks_embedding', 'blocks', ['embedding'], postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, schema='public')
    op.create_index('ix_blocks_fts', 'blocks', [sa.text("to_tsvector('english', content)")], postgresql_using='gin', schema='public')
    op.create_index('ix_blocks_heading', 'blocks', ['tenant_id', 'heading_path'], schema='public')

    # entities
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('canonical_name', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_unique_constraint('uq_entities_tenant_type_canonical', 'entities', ['tenant_id', 'entity_type', 'canonical_name'], schema='public')
    op.create_index('ix_entities_tenant', 'entities', ['tenant_id'], schema='public')

    # facts
    op.create_table(
        'facts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('predicate', sa.Text(), nullable=False),
        sa.Column('object_value', postgresql.JSONB(), nullable=False),
        sa.Column('object_type', sa.Text(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('retracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_episode_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('episodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_block_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default='{}', nullable=False),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('source_version', sa.Text(), nullable=True),
        sa.Column('source_status', sa.Text(), nullable=False),
        sa.Column('authority_rank', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('status', sa.Text(), server_default='active', nullable=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_by_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index('ix_facts_tenant', 'facts', ['tenant_id'], schema='public')
    op.create_index('ix_facts_subject_predicate', 'facts', ['subject_entity_id', 'predicate'], schema='public')
    op.create_index('ix_facts_valid_time', 'facts', ['valid_from', 'valid_to'], schema='public')
    op.create_index('ix_facts_txn_time', 'facts', ['recorded_at', 'retracted_at'], schema='public')
    op.create_index('ix_facts_authority', 'facts', ['authority_rank'], schema='public')
    op.create_index('ix_facts_status', 'facts', ['status'], schema='public', postgresql_where=sa.text("status IN ('active', 'conflict', 'pending_review')"))

    # GiST range indexes for temporal queries
    op.execute("""
        CREATE INDEX ix_facts_valid_range ON facts USING gist (
            tenant_id,
            daterange(valid_from, COALESCE(valid_to, 'infinity'::DATE), '[]')
        );
    """)
    op.execute("""
        CREATE INDEX ix_facts_txn_range ON facts USING gist (
            tenant_id,
            tsrange(recorded_at, COALESCE(retracted_at, 'infinity'::TIMESTAMPTZ), '[]')
        );
    """)

    # conflicts
    op.create_table(
        'conflicts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fact_id_1', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fact_id_2', postgresql.UUID(as_uuid=True), sa.ForeignKey('facts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conflict_type', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='open', nullable=False),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index('ix_conflicts_tenant', 'conflicts', ['tenant_id'], schema='public')
    op.create_index('ix_conflicts_status', 'conflicts', ['status'], schema='public', postgresql_where=sa.text("status = 'open'"))

    # jobs
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.Text(), server_default='queued', nullable=False),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index(
        'ix_jobs_tenant_status_scheduled',
        'jobs',
        ['tenant_id', 'status', 'scheduled_for'],
        schema='public',
        postgresql_where=sa.text("status IN ('queued', 'retrying')")
    )

    # answer_logs
    op.create_table(
        'answer_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('client_desk', sa.Text(), nullable=True),
        sa.Column('as_of_date', sa.Date(), nullable=True),
        sa.Column('route', sa.Text(), nullable=False),
        sa.Column('answer_markdown', sa.Text(), nullable=True),
        sa.Column('citations', postgresql.JSONB(), nullable=True),
        sa.Column('calculator_outputs', postgresql.JSONB(), nullable=True),
        sa.Column('verifier_result', postgresql.JSONB(), nullable=True),
        sa.Column('escalated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_index('ix_answer_logs_tenant', 'answer_logs', ['tenant_id'], schema='public')
    op.create_index('ix_answer_logs_created', 'answer_logs', ['created_at'], schema='public')

    # users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('hashed_password', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        schema='public'
    )
    op.create_unique_constraint('uq_users_tenant_email', 'users', ['tenant_id', 'email'], schema='public')
    op.create_index('ix_users_tenant', 'users', ['tenant_id'], schema='public')


def downgrade() -> None:
    op.drop_table('users', schema='public')
    op.drop_table('answer_logs', schema='public')
    op.drop_table('jobs', schema='public')
    op.drop_table('conflicts', schema='public')
    op.drop_table('facts', schema='public')
    op.drop_table('entities', schema='public')
    op.drop_table('blocks', schema='public')
    op.drop_table('episodes', schema='public')
    op.drop_table('tenants', schema='public')