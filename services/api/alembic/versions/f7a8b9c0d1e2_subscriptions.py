"""subscriptions: Source feed columns + emitted_by + feed_entries table

Revision ID: f7a8b9c0d1e2
Revises: 1e2f3a4b5c6d
"""
import sqlalchemy as sa
from alembic import op

revision = 'f7a8b9c0d1e2'
down_revision = '1e2f3a4b5c6d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE captured_via ADD VALUE IF NOT EXISTS 'feed'")

    op.add_column('sources', sa.Column('feed_url', sa.String(), nullable=True))
    op.create_index(op.f('ix_sources_feed_url'), 'sources', ['feed_url'])
    op.add_column('sources', sa.Column('muted', sa.Boolean(), nullable=True))
    op.add_column('sources', sa.Column('last_fetch_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sources', sa.Column('last_fetch_error', sa.Text(), nullable=True))
    op.add_column('sources', sa.Column('feed_etag', sa.String(), nullable=True))
    op.add_column('sources', sa.Column('feed_http_modified', sa.String(), nullable=True))
    op.add_column('sources', sa.Column('consecutive_failures', sa.Integer(), nullable=True))
    op.add_column('sources', sa.Column('emitted_by', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_sources_emitted_by'), 'sources', ['emitted_by'])
    op.create_foreign_key(
        'fk_sources_emitted_by', 'sources', 'sources',
        ['emitted_by'], ['id'], ondelete='SET NULL',
    )

    op.create_table(
        'feed_entries',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('subscription_id', sa.Uuid(), nullable=False),
        sa.Column('guid', sa.String(length=512), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('promoted_source_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['promoted_source_id'], ['sources.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('subscription_id', 'guid', name='uq_feed_entries_sub_guid'),
    )
    op.create_index(
        op.f('ix_feed_entries_subscription_id'), 'feed_entries', ['subscription_id']
    )


def downgrade() -> None:
    op.drop_table('feed_entries')
    op.drop_constraint('fk_sources_emitted_by', 'sources', type_='foreignkey')
    op.drop_index(op.f('ix_sources_emitted_by'), table_name='sources')
    op.drop_column('sources', 'emitted_by')
    op.drop_column('sources', 'consecutive_failures')
    op.drop_column('sources', 'feed_http_modified')
    op.drop_column('sources', 'feed_etag')
    op.drop_column('sources', 'last_fetch_error')
    op.drop_column('sources', 'last_fetch_at')
    op.drop_column('sources', 'muted')
    op.drop_index(op.f('ix_sources_feed_url'), table_name='sources')
    op.drop_column('sources', 'feed_url')
    # 'feed' stays in captured_via — enum value removal needs a type rebuild
    # and no rows can carry it after feed_entries drops; tolerated leftover.
