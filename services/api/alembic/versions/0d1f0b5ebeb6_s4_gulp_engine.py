"""s4 gulp engine

Adds the S4 "Gulp Mode" schema: SM-2-lite scheduling + mastery-ladder columns
on `cards`, the append-only `review_events` log, the `gulp_sessions` table,
and `users.gulp_session_minutes`.

`mastery_ladder` is created explicitly (checkfirst) before it's used on
`op.add_column('cards', ...)` — Postgres only auto-creates an enum type via
the DDL events fired by `Table.create()`/`Table.drop()`, which `add_column`
does not go through. The other three enums (`session_scope`,
`session_status`, `review_grade`) are only ever used inside `op.create_table`
calls, so SQLAlchemy creates/drops them automatically as part of those.

Revision ID: 0d1f0b5ebeb6
Revises: b8c9d0e1f2a3
"""
import sqlalchemy as sa
from alembic import op

revision = '0d1f0b5ebeb6'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── enums ──
    mastery_ladder = sa.Enum(
        "unread", "read", "summarized", "can_recall",
        "can_distinguish", "can_apply", "mastered", name="mastery_ladder",
        create_type=False,
    )
    mastery_ladder.create(op.get_bind(), checkfirst=True)

    # ── cards: SM-2-lite scheduling fold + mastery ladder ──
    # NOT NULL columns with no natural zero-value need a server_default to
    # backfill existing rows (this table is not empty pre-migration); it's
    # dropped right after so the DB doesn't carry a stale default long-term
    # — matches the pattern in a1b2c3d4e5f6_s2_paper_report_contract.py.
    op.add_column('cards', sa.Column('interval_days', sa.Float(), nullable=False, server_default='0'))
    op.add_column('cards', sa.Column('ease', sa.Float(), nullable=False, server_default='2.3'))
    op.add_column('cards', sa.Column('next_review_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cards', sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cards', sa.Column('reps', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('cards', sa.Column('lapses', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('cards', sa.Column('stability', sa.Float(), nullable=True))
    op.add_column('cards', sa.Column('difficulty', sa.Float(), nullable=True))
    op.add_column('cards', sa.Column('ladder', mastery_ladder, nullable=True))
    op.add_column('cards', sa.Column('mastery_updated_at', sa.DateTime(timezone=True), nullable=True))
    for col in ('interval_days', 'ease', 'reps', 'lapses'):
        op.alter_column('cards', col, server_default=None)
    op.create_index(op.f('ix_cards_next_review_at'), 'cards', ['next_review_at'], unique=False)

    # ── users: per-user daily session length ──
    op.add_column('users', sa.Column('gulp_session_minutes', sa.Integer(), nullable=False, server_default='5'))
    op.alter_column('users', 'gulp_session_minutes', server_default=None)

    # ── gulp_sessions (must precede review_events for the FK) ──
    op.create_table('gulp_sessions',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('scope_type', sa.Enum('daily', 'knowledge_base', 'concept', 'free_explore', 'at_risk', name='session_scope'), nullable=False),
    sa.Column('scope_ref', sa.Uuid(), nullable=True),
    sa.Column('target_minutes', sa.Integer(), nullable=False),
    sa.Column('planned_card_ids', sa.JSON(), nullable=False),
    sa.Column('status', sa.Enum('building', 'active', 'complete', 'abandoned', name='session_status'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gulp_sessions_owner_id'), 'gulp_sessions', ['owner_id'], unique=False)

    # ── review_events (append-only log; FKs into gulp_sessions + cards) ──
    op.create_table('review_events',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('session_id', sa.Uuid(), nullable=False),
    sa.Column('card_id', sa.Uuid(), nullable=False),
    sa.Column('grade', sa.Enum('got_it', 'fuzzy', 'missed', name='review_grade'), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['gulp_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_review_events_card_id'), 'review_events', ['card_id'], unique=False)
    op.create_index(op.f('ix_review_events_owner_id'), 'review_events', ['owner_id'], unique=False)
    op.create_index(op.f('ix_review_events_session_id'), 'review_events', ['session_id'], unique=False)


def downgrade() -> None:
    # ── tables (review_events before gulp_sessions: FK) ──
    op.drop_index(op.f('ix_review_events_session_id'), table_name='review_events')
    op.drop_index(op.f('ix_review_events_owner_id'), table_name='review_events')
    op.drop_index(op.f('ix_review_events_card_id'), table_name='review_events')
    op.drop_table('review_events')
    op.drop_index(op.f('ix_gulp_sessions_owner_id'), table_name='gulp_sessions')
    op.drop_table('gulp_sessions')

    # ── users ──
    op.drop_column('users', 'gulp_session_minutes')

    # ── cards ──
    op.drop_index(op.f('ix_cards_next_review_at'), table_name='cards')
    op.drop_column('cards', 'mastery_updated_at')
    op.drop_column('cards', 'ladder')
    op.drop_column('cards', 'difficulty')
    op.drop_column('cards', 'stability')
    op.drop_column('cards', 'lapses')
    op.drop_column('cards', 'reps')
    op.drop_column('cards', 'last_reviewed_at')
    op.drop_column('cards', 'next_review_at')
    op.drop_column('cards', 'ease')
    op.drop_column('cards', 'interval_days')

    # ── enums ──
    # session_scope/session_status/review_grade were only ever embedded in
    # create_table calls above, so their DROP TABLE already dropped the
    # types via SQLAlchemy's DDL events; drop them explicitly too
    # (checkfirst-guarded) so downgrade is correct even if that ever changes.
    sa.Enum(name='review_grade').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='session_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='session_scope').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='mastery_ladder').drop(op.get_bind(), checkfirst=True)
