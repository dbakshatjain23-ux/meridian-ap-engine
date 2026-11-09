"""Seed Meridian AP ontology data.

Revision ID: 003
Revises: 002
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import date, datetime
import uuid

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration seeds the Meridian AP ontology
    # In production, would use the seed_meridian.py script
    # This is a placeholder for the migration structure
    pass


def downgrade() -> None:
    # Would delete seeded data
    pass