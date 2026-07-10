"""user system: users email/password_hash (+ dev backfill), concept owner_id

Revision ID: a9b0c1d2e3f4
Revises: 033e0b57ef69
"""

import sqlalchemy as sa
from alembic import op
from argon2 import PasswordHasher

revision = "a9b0c1d2e3f4"
down_revision = "033e0b57ef69"
branch_labels = None
depends_on = None

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
# NB: not a .local/.test/.invalid domain — pydantic's EmailStr (email-validator)
# rejects special-use TLDs, which would make the dev account unable to log in.
DEV_EMAIL = "dev@example.com"
DEV_PASSWORD = "gulp-dev-2026"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. users: add credentials nullable, backfill, then enforce.
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    conn.execute(
        sa.text("UPDATE users SET email = :e, password_hash = :h WHERE id = :id"),
        {"e": DEV_EMAIL, "h": PasswordHasher().hash(DEV_PASSWORD), "id": DEV_USER_ID},
    )
    # Defensive: any other pre-existing user rows get a placeholder (cannot log in).
    conn.execute(
        sa.text("UPDATE users SET email = 'user-' || id || '@example.invalid' WHERE email IS NULL")
    )
    conn.execute(sa.text("UPDATE users SET password_hash = '' WHERE password_hash IS NULL"))
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "password_hash", nullable=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. concept graph: add owner_id nullable, backfill to dev user, enforce + FK.
    for table in ("concepts", "concept_edges"):
        op.add_column(table, sa.Column("owner_id", sa.Uuid(), nullable=True))
        conn.execute(
            sa.text(f"UPDATE {table} SET owner_id = :id WHERE owner_id IS NULL"),
            {"id": DEV_USER_ID},
        )
        op.alter_column(table, "owner_id", nullable=False)
        op.create_index(op.f(f"ix_{table}_owner_id"), table, ["owner_id"])
        op.create_foreign_key(f"fk_{table}_owner_id", table, "users", ["owner_id"], ["id"])


def downgrade() -> None:
    for table in ("concept_edges", "concepts"):
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_owner_id"), table_name=table)
        op.drop_column(table, "owner_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
