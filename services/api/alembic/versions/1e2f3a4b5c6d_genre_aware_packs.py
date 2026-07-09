"""genre-aware packs: Source.genre + KnowledgePack thin base (pack_type/summary/extras)

Revision ID: 1e2f3a4b5c6d
Revises: 0d1f0b5ebeb6
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '1e2f3a4b5c6d'
down_revision = '0d1f0b5ebeb6'
branch_labels = None
depends_on = None

_BLOCK_TYPES = ('prose', 'formula', 'table', 'figure', 'list')


def upgrade() -> None:
    # PG 12+: ADD VALUE works inside a transaction as long as the new value
    # isn't used in the same transaction (we don't write code blocks here).
    op.execute("ALTER TYPE pack_block_type ADD VALUE IF NOT EXISTS 'code'")

    # --- sources.genre --------------------------------------------------
    sa.Enum('paper', 'article', 'note', name='source_genre').create(op.get_bind())
    op.add_column(
        'sources',
        sa.Column('genre', postgresql.ENUM(name='source_genre', create_type=False), nullable=True),
    )
    # Backfill with the same heuristics the worker classifier applies; genre
    # describes the source, so this is honest even where the existing pack is
    # a paper report of a non-paper (re-processing corrects the pack).
    op.execute("""
        UPDATE sources SET genre = (CASE
            WHEN origin_url IS NULL THEN 'note'
            WHEN origin_url ILIKE '%arxiv.org%' OR origin_url ILIKE '%openreview.net%'
                THEN 'paper'
            WHEN media_type = 'pdf' THEN 'paper'
            ELSE 'article' END)::source_genre
        WHERE kind = 'snapshot'
    """)

    # --- knowledge_packs: thin base + extras ----------------------------
    sa.Enum('paper', 'article', name='pack_type').create(op.get_bind())
    op.add_column(
        'knowledge_packs',
        sa.Column('pack_type', postgresql.ENUM(name='pack_type', create_type=False), nullable=True),
    )
    op.add_column('knowledge_packs', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column(
        'knowledge_packs',
        sa.Column('extras', sa.JSON(), nullable=False, server_default='{}'),
    )
    # Every existing pack IS a paper report; move its fields into extras.
    op.execute("""
        UPDATE knowledge_packs SET pack_type = 'paper',
            extras = json_build_object(
                'key_insight', key_insight,
                'core_contributions', core_contributions,
                'references', "references")
    """)
    op.alter_column('knowledge_packs', 'pack_type', nullable=False)
    op.drop_column('knowledge_packs', 'key_insight')
    op.drop_column('knowledge_packs', 'core_contributions')
    op.drop_column('knowledge_packs', 'references')


def downgrade() -> None:
    op.add_column('knowledge_packs', sa.Column('key_insight', sa.Text(), nullable=True))
    op.add_column('knowledge_packs', sa.Column('core_contributions', sa.JSON(), nullable=True))
    op.add_column('knowledge_packs', sa.Column('references', sa.JSON(), nullable=True))
    op.execute("""
        UPDATE knowledge_packs SET
            key_insight = COALESCE(extras ->> 'key_insight', ''),
            core_contributions = COALESCE(extras -> 'core_contributions', '[]'::json),
            "references" = COALESCE(extras -> 'references', '[]'::json)
    """)
    op.alter_column('knowledge_packs', 'key_insight', nullable=False)
    op.drop_column('knowledge_packs', 'extras')
    op.drop_column('knowledge_packs', 'summary')
    op.drop_column('knowledge_packs', 'pack_type')
    op.execute('DROP TYPE pack_type')
    op.drop_column('sources', 'genre')
    op.execute('DROP TYPE source_genre')
    # Rebuild pack_block_type without 'code' — safe only while no code blocks
    # exist (delete article packs first if downgrading past this point).
    op.execute("ALTER TYPE pack_block_type RENAME TO pack_block_type_old")
    sa.Enum(*_BLOCK_TYPES, name='pack_block_type').create(op.get_bind())
    op.execute(
        "ALTER TABLE pack_blocks ALTER COLUMN block_type TYPE pack_block_type "
        "USING block_type::text::pack_block_type"
    )
    op.execute("DROP TYPE pack_block_type_old")
