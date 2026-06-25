"""Digest stage: NormDoc -> DigestResult via the LLM service (one turn).

Single-pass with a budget guard (S2 design C13 v1): content over
MAX_DIGEST_CHARS is truncated and the pack is flagged low-confidence.
Per-section map-reduce for long content is a later enhancement.
"""

from app.llm import ModelConfig, complete_structured
from app.llm.base import LLMProvider
from app.pipeline.normdoc import NormDoc
from app.pipeline.schemas import DigestResult
from app.prompts.digest import build_digest_messages
from gulp_shared.settings import settings  # type: ignore[import-untyped]

# ~12k tokens of input; tunable. Over this, we digest a prefix and flag it.
MAX_DIGEST_CHARS = 48_000
_TRUNCATED_CONFIDENCE_CAP = 0.5


async def run_digest(
    normdoc: NormDoc,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> DigestResult:
    cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)
    body = normdoc.content_body
    truncated = len(body) > MAX_DIGEST_CHARS
    if truncated:
        body = body[:MAX_DIGEST_CHARS]
    system, messages = build_digest_messages(normdoc, body)
    result = await complete_structured(
        response_model=DigestResult,
        system=system,
        messages=messages,
        config=cfg,
        provider=provider,
    )
    if truncated and result.confidence > _TRUNCATED_CONFIDENCE_CAP:
        result.confidence = _TRUNCATED_CONFIDENCE_CAP
    return result
