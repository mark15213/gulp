"""Pipeline orchestration: Source -> (fetch -> adapt -> digest -> persist) -> status.

Testable in isolation: pass an injected `fetch` and `provider`. The arq entry
(app/tasks) provides the real ones and a real DB session.
"""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.llm.base import LLMProvider, ModelConfig
from app.pipeline.adapters.note import note_to_normdoc
from app.pipeline.adapters.webpage import fetch_html, webpage_to_normdoc
from app.pipeline.digest import run_digest
from app.pipeline.normdoc import NormDoc
from app.pipeline.persist import persist_pack
from gulp_shared.models.source import MediaType, SnapshotStatus, Source  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[str]]


class PipelineError(Exception):
    """A processing failure that should land the snapshot in needs_attention."""


async def _to_normdoc(source: Source, fetch: FetchFn) -> NormDoc:
    if source.origin_url:
        html = await fetch(source.origin_url)
        return webpage_to_normdoc(html, fallback_title=source.title, url=source.origin_url)
    return note_to_normdoc(source.title, source.content_body or "")


async def process_source(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_html,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> None:
    source.status = SnapshotStatus.processing
    db.commit()
    try:
        normdoc = await _to_normdoc(source, fetch)
        if not normdoc.content_body.strip():
            raise PipelineError("extraction produced no content")
        source.content_body = normdoc.content_body
        source.media_type = MediaType(normdoc.media_type)
        digest = await run_digest(normdoc, provider=provider, config=config)
        persist_pack(db, source, digest)
        source.status = SnapshotStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.needs_attention
        db.commit()
        logger.exception("process_snapshot failed for %s", source.id)
