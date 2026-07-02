"""card types consolidation: 6 types -> flashcard/mcq/cloze

Collapses the free-response cluster (short_answer/explain/apply/recall) into a
single `flashcard` type; keeps mcq + cloze. Swaps the Postgres enum via a
rename-create-swap-drop so the old values are removed (not just hidden), and
remaps existing rows in the ALTER ... USING clause.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
import sqlalchemy as sa
from alembic import op

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None

_NEW = ('flashcard', 'mcq', 'cloze')
_OLD = ('short_answer', 'mcq', 'cloze', 'explain', 'apply', 'recall')


def upgrade() -> None:
    op.execute("ALTER TYPE card_type RENAME TO card_type_old")
    sa.Enum(*_NEW, name='card_type').create(op.get_bind())
    op.execute(
        "ALTER TABLE cards ALTER COLUMN card_type TYPE card_type USING ("
        "  CASE card_type::text"
        "    WHEN 'short_answer' THEN 'flashcard'"
        "    WHEN 'explain' THEN 'flashcard'"
        "    WHEN 'apply' THEN 'flashcard'"
        "    WHEN 'recall' THEN 'flashcard'"
        "    ELSE card_type::text"
        "  END::card_type)"
    )
    op.execute("DROP TYPE card_type_old")


def downgrade() -> None:
    # Lossy: every flashcard becomes a short_answer (the pre-merge default).
    op.execute("ALTER TYPE card_type RENAME TO card_type_new")
    sa.Enum(*_OLD, name='card_type').create(op.get_bind())
    op.execute(
        "ALTER TABLE cards ALTER COLUMN card_type TYPE card_type USING ("
        "  CASE card_type::text"
        "    WHEN 'flashcard' THEN 'short_answer'"
        "    ELSE card_type::text"
        "  END::card_type)"
    )
    op.execute("DROP TYPE card_type_new")
