"""Digest stage: NormDoc -> PaperReport via the LLM service (one turn).

Single-pass with a budget guard: content over MAX_DIGEST_CHARS is truncated
before sending. Per-section map-reduce for long content is a later enhancement.
"""

from gulp_shared.llm import ModelConfig, complete_structured
from gulp_shared.llm.base import LLMProvider

from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import PaperReport
from app.prompts.digest import build_digest_messages

# ~12k tokens of input; tunable. Over this, we digest a prefix.
MAX_DIGEST_CHARS = 48_000


async def run_digest(
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> PaperReport:
    cfg = config or ModelConfig()
    body = normdoc.content_body
    if len(body) > MAX_DIGEST_CHARS:
        body = body[:MAX_DIGEST_CHARS]
    system, messages = build_digest_messages(normdoc, body)
    return await complete_structured(
        response_model=PaperReport,
        system=system,
        messages=messages,
        config=cfg,
        provider=provider,
    )
