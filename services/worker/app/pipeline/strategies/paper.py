"""Paper strategy — the LLM deep-read: digest the source into a PaperReport."""

from gulp_shared.llm.base import LLMProvider, ModelConfig

from app.pipeline.digest import run_digest
from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import PackDraft, draft_from_paper_report


async def build_paper_draft(
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> PackDraft:
    report = await run_digest(normdoc, provider=provider, config=config)
    return draft_from_paper_report(report)
