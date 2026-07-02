"""cards supply: CardOrigin.imported + sources.cards_status

Revision ID: e5f6a7b8c9d0
Revises: c2d3e4f5a6b7
"""
import sqlalchemy as sa
from alembic import op

revision = 'e5f6a7b8c9d0'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE card_origin ADD VALUE IF NOT EXISTS 'imported'")
    cards_status = sa.Enum('generating', 'ready', 'failed', name='cards_status')
    cards_status.create(op.get_bind(), checkfirst=True)
    op.add_column('sources', sa.Column('cards_status', cards_status, nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'cards_status')
    op.execute("DROP TYPE IF EXISTS cards_status")
    # PostgreSQL has no DROP VALUE; 'imported' is left on card_origin.
