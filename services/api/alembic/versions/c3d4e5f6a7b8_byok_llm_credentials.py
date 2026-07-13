"""byok: user_llm_credentials table + users default provider/model

Revision ID: c3d4e5f6a7b8
Revises: a9b0c1d2e3f4
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_llm_credentials_user_provider"),
    )
    op.create_index(op.f("ix_user_llm_credentials_user_id"), "user_llm_credentials", ["user_id"])
    op.add_column("users", sa.Column("llm_provider", sa.String(), nullable=True))
    op.add_column("users", sa.Column("llm_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "llm_model")
    op.drop_column("users", "llm_provider")
    op.drop_index(op.f("ix_user_llm_credentials_user_id"), table_name="user_llm_credentials")
    op.drop_table("user_llm_credentials")
