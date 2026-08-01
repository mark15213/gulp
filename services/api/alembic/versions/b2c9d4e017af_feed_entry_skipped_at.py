"""feed_entries.skipped_at — explicit triage dismissal

Spec 2026-08-01 (feeds/inbox triage) §2. Triage state stays *derived*:
forwarded (promoted_source_id) > skipped (skipped_at) > pending. No backfill —
entries that were merely "read" stay pending and can be cleared with Skip all.

Revision ID: b2c9d4e017af
Revises: 05383dfd1b81
"""
import sqlalchemy as sa
from alembic import op

revision = 'b2c9d4e017af'
down_revision = '05383dfd1b81'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'feed_entries',
        sa.Column('skipped_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('feed_entries', 'skipped_at')
