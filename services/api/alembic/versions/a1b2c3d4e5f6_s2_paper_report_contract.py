"""s2 paper report contract

Revision ID: a1b2c3d4e5f6
Revises: b14db36cfeec
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'b14db36cfeec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop facets entirely.
    op.drop_index('ix_pack_elements_pack_id', table_name='pack_elements')
    op.drop_index('ix_pack_elements_concept_id', table_name='pack_elements')
    op.drop_table('pack_elements')
    op.execute("DROP TYPE IF EXISTS pack_element_type")
    op.execute("DROP TYPE IF EXISTS pack_element_state")

    # 2. knowledge_packs: narrative columns -> paper-report fields.
    op.drop_column('knowledge_packs', 'summary')
    op.drop_column('knowledge_packs', 'background')
    op.drop_column('knowledge_packs', 'confidence')
    op.add_column('knowledge_packs', sa.Column('title', sa.Text(), nullable=False, server_default=''))
    op.add_column('knowledge_packs', sa.Column('key_insight', sa.Text(), nullable=False, server_default=''))
    op.add_column('knowledge_packs', sa.Column('core_contributions', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('knowledge_packs', sa.Column('references', sa.JSON(), nullable=False, server_default='[]'))
    for col in ('title', 'key_insight', 'core_contributions', 'references'):
        op.alter_column('knowledge_packs', col, server_default=None)

    # 3. pack_blocks: content/anchor columns -> a single JSON `data`.
    op.drop_index('ix_pack_blocks_anchor_id', table_name='pack_blocks')
    op.drop_column('pack_blocks', 'content')
    op.drop_column('pack_blocks', 'content_ref')
    op.drop_column('pack_blocks', 'source_anchor')
    op.drop_column('pack_blocks', 'anchor_id')
    op.add_column('pack_blocks', sa.Column('data', sa.JSON(), nullable=False, server_default='{}'))
    op.alter_column('pack_blocks', 'data', server_default=None)

    # 4. Swap the block-type enum: callout/quote -> formula/table/list.
    # Purge any existing rows with block types that don't exist in the new enum.
    op.execute("DELETE FROM pack_blocks WHERE block_type::text NOT IN ('prose', 'figure')")
    op.execute("ALTER TYPE pack_block_type RENAME TO pack_block_type_old")
    op.execute("CREATE TYPE pack_block_type AS ENUM ('prose', 'formula', 'table', 'figure', 'list')")
    op.execute(
        "ALTER TABLE pack_blocks ALTER COLUMN block_type TYPE pack_block_type "
        "USING block_type::text::pack_block_type"
    )
    op.execute("DROP TYPE pack_block_type_old")


def downgrade() -> None:
    # Reverse 4.
    op.execute("ALTER TYPE pack_block_type RENAME TO pack_block_type_new")
    op.execute("CREATE TYPE pack_block_type AS ENUM ('prose', 'figure', 'callout', 'quote')")
    op.execute(
        "ALTER TABLE pack_blocks ALTER COLUMN block_type TYPE pack_block_type "
        "USING block_type::text::pack_block_type"
    )
    op.execute("DROP TYPE pack_block_type_new")

    # Reverse 3.
    op.add_column('pack_blocks', sa.Column('content', sa.Text(), nullable=True))
    op.add_column('pack_blocks', sa.Column('content_ref', sa.String(), nullable=True))
    op.add_column('pack_blocks', sa.Column('source_anchor', sa.JSON(), nullable=True))
    op.add_column('pack_blocks', sa.Column('anchor_id', sa.String(), nullable=False, server_default=''))
    op.alter_column('pack_blocks', 'anchor_id', server_default=None)
    op.drop_column('pack_blocks', 'data')
    op.create_index('ix_pack_blocks_anchor_id', 'pack_blocks', ['anchor_id'], unique=False)

    # Reverse 2.
    op.add_column('knowledge_packs', sa.Column('summary', sa.Text(), nullable=False, server_default=''))
    op.alter_column('knowledge_packs', 'summary', server_default=None)
    op.add_column('knowledge_packs', sa.Column('background', sa.Text(), nullable=True))
    op.add_column('knowledge_packs', sa.Column('confidence', sa.Float(), nullable=True))
    op.drop_column('knowledge_packs', 'references')
    op.drop_column('knowledge_packs', 'core_contributions')
    op.drop_column('knowledge_packs', 'key_insight')
    op.drop_column('knowledge_packs', 'title')

    # Reverse 1.
    op.create_table(
        'pack_elements',
        sa.Column('pack_id', sa.Uuid(), nullable=False),
        sa.Column('element_type', sa.Enum('key_term', 'person_org', 'claim', 'counter_view', 'connection', name='pack_element_type'), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('concept_id', sa.Uuid(), nullable=True),
        sa.Column('block_id', sa.Uuid(), nullable=True),
        sa.Column('section_label', sa.String(), nullable=True),
        sa.Column('state', sa.Enum('suggested', 'kept', 'dismissed', name='pack_element_state'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['block_id'], ['pack_blocks.id'], ),
        sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
        sa.ForeignKeyConstraint(['pack_id'], ['knowledge_packs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pack_elements_concept_id', 'pack_elements', ['concept_id'], unique=False)
    op.create_index('ix_pack_elements_pack_id', 'pack_elements', ['pack_id'], unique=False)
