"""single-gate lifecycle: drop awaiting_review/in_library from snapshot_status

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
import sqlalchemy as sa
from alembic import op

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None

_KEPT = ('queued', 'unprocessed', 'processing', 'ready', 'exported', 'needs_attention')
_FULL = _KEPT + ('awaiting_review', 'in_library')


def _rebuild(values: tuple[str, ...]) -> None:
    # No rows ever held the dropped values (verified pre-migration; nothing
    # writes them), so a plain type swap is safe.
    op.execute("ALTER TYPE snapshot_status RENAME TO snapshot_status_old")
    sa.Enum(*values, name='snapshot_status').create(op.get_bind())
    op.execute(
        "ALTER TABLE sources ALTER COLUMN status TYPE snapshot_status "
        "USING status::text::snapshot_status"
    )
    op.execute("DROP TYPE snapshot_status_old")


def upgrade() -> None:
    _rebuild(_KEPT)


def downgrade() -> None:
    _rebuild(_FULL)
