"""s2 pack cascade delete

Revision ID: c2d3e4f5a6b7
Revises: d3e4f5a6b7c8
"""
from alembic import op

revision = 'c2d3e4f5a6b7'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Re-importing a result replaces a snapshot's pack by deleting the old one;
    # its pack_sections/pack_blocks must go with it. The original FKs were created
    # without ON DELETE, so deleting a knowledge_pack raised a ForeignKeyViolation
    # (pack_sections still referenced it). Recreate them as ON DELETE CASCADE.
    op.drop_constraint('pack_blocks_section_id_fkey', 'pack_blocks', type_='foreignkey')
    op.create_foreign_key(
        'pack_blocks_section_id_fkey', 'pack_blocks', 'pack_sections',
        ['section_id'], ['id'], ondelete='CASCADE',
    )
    op.drop_constraint('pack_sections_pack_id_fkey', 'pack_sections', type_='foreignkey')
    op.create_foreign_key(
        'pack_sections_pack_id_fkey', 'pack_sections', 'knowledge_packs',
        ['pack_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('pack_sections_pack_id_fkey', 'pack_sections', type_='foreignkey')
    op.create_foreign_key(
        'pack_sections_pack_id_fkey', 'pack_sections', 'knowledge_packs',
        ['pack_id'], ['id'],
    )
    op.drop_constraint('pack_blocks_section_id_fkey', 'pack_blocks', type_='foreignkey')
    op.create_foreign_key(
        'pack_blocks_section_id_fkey', 'pack_blocks', 'pack_sections',
        ['section_id'], ['id'],
    )
