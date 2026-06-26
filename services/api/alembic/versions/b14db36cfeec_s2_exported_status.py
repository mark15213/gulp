"""s2 exported status

Revision ID: b14db36cfeec
Revises: cb5fcc8902ba
"""
from alembic import op
import sqlalchemy as sa


revision = 'b14db36cfeec'
down_revision = 'cb5fcc8902ba'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE snapshot_status ADD VALUE IF NOT EXISTS 'exported'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE; the enum value is left in place.
    pass
