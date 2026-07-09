"""Per-genre pack production strategies (S2 design: genre -> strategy).

`build_pack_draft` is the single entry the pipeline calls: papers get the LLM
deep-read; every other genre — article, note, and any future/unknown value —
falls back to the deterministic preserve strategy, so the worst case is
"no enrichment", never a misrepresenting rewrite.
"""

from gulp_shared.llm.base import LLMProvider, ModelConfig
from gulp_shared.models.source import SourceGenre

from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import PackDraft
from app.pipeline.strategies.paper import build_paper_draft
from app.pipeline.strategies.preserve import build_preserve_draft


async def build_pack_draft(
    genre: SourceGenre | None,
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> PackDraft:
    if genre is SourceGenre.paper:
        return await build_paper_draft(normdoc, provider=provider, config=config)
    return build_preserve_draft(normdoc)
