"""s2 pack block messages

Revision ID: d3e4f5a6b7c8
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b7c8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pack_block_messages',
        sa.Column('block_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('user', 'assistant', name='chat_role'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['block_id'], ['pack_blocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_pack_block_messages_block_id'), 'pack_block_messages', ['block_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_pack_block_messages_block_id'), table_name='pack_block_messages')
    op.drop_table('pack_block_messages')
    op.execute("DROP TYPE IF EXISTS chat_role")
