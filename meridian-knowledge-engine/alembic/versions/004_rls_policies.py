"""Row Level Security policies for multi-tenancy.

Revision ID: 004
Revises: 003
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable RLS on all tenant-isolated tables
    tables = [
        'episodes', 'blocks', 'entities', 'facts', 
        'conflicts', 'jobs', 'answer_logs', 'users'
    ]

    for table in tables:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;')

    # Create policy function
    op.execute("""
        CREATE OR REPLACE FUNCTION current_tenant_id() 
        RETURNS uuid LANGUAGE sql STABLE AS $$
            SELECT current_setting('app.current_tenant_id', true)::uuid
        $$;
    """)

    # Create RLS policies for each table
    tables_with_tenant = [
        'episodes', 'blocks', 'entities', 'facts', 
        'conflicts', 'jobs', 'answer_logs', 'users'
    ]

    for table in tables_with_tenant:
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            USING (tenant_id = current_tenant_id())
            WITH CHECK (tenant_id = current_tenant_id());
        """)


def downgrade() -> None:
    tables = ['episodes', 'blocks', 'entities', 'facts', 'conflicts', 'jobs', 'answer_logs', 'users']
    for table in tables:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON {table};')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;')
    
    op.execute('DROP FUNCTION IF EXISTS current_tenant_id();')