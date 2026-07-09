"""Pipeline orchestration: Source -> (fetch -> adapt -> digest -> persist) -> status.

Testable in isolation: pass an injected `fetch` and `provider`. The arq entry
(app/tasks) provides the real ones and a real DB session.
"""

import logging
from collections.abc import Awaitable, Callable

from gulp_shared.llm.base import LLMProvider, ModelConfig
from gulp_shared.models.source import (
    MediaType,
    SnapshotStatus,
    Source,
)
from gulp_shared.urls import host_of
from sqlalchemy.orm import Session

from app.pipeline.adapters.fetch import FetchedDoc, fetch_document, is_pdf
from app.pipeline.adapters.note import note_to_normdoc
from app.pipeline.classify import detect_genre
from app.pipeline.adapters.pdf import pdf_to_normdoc
from app.pipeline.adapters.webpage import webpage_to_normdoc
from app.pipeline.digest import run_digest
from app.pipeline.figures.run import extract_arxiv_figures
from app.pipeline.normdoc import NormDoc
from app.pipeline.persist import persist_pack
from app.pipeline.schemas import draft_from_paper_report

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


class PipelineError(Exception):
    """A processing failure that should land the snapshot in needs_attention."""


def normdoc_from_fetched(doc: FetchedDoc, *, fallback_title: str, url: str) -> NormDoc:
    if is_pdf(doc):
        return pdf_to_normdoc(doc.content, fallback_title=fallback_title, url=url)
    html = doc.content.decode("utf-8", errors="replace")
    return webpage_to_normdoc(html, fallback_title=fallback_title, url=url)


async def _to_normdoc(source: Source, fetch: FetchFn) -> NormDoc:
    if source.origin_url:
        doc = await fetch(source.origin_url)
        return normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)
    return note_to_normdoc(source.title, source.content_body or "")


async def process_source(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_document,
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
        if source.genre is None:  # never overwrite a user's correction
            source.genre = detect_genre(source.origin_url, normdoc.media_type)
        if (
            source.origin_url
            and source.title == host_of(source.origin_url)
            and normdoc.title
            and normdoc.title != source.title
        ):
            source.title = normdoc.title
        digest = await run_digest(normdoc, provider=provider, config=config)
        persist_pack(db, source, draft_from_paper_report(digest))
        source.status = SnapshotStatus.ready
        db.commit()
        await _maybe_extract_figures(db, source, fetch)
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.needs_attention
        db.commit()
        logger.exception("process_snapshot failed for %s", source.id)


async def _maybe_extract_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    """Best-effort: the pack is already `ready`; a figure failure must not change that."""
    try:
        await extract_arxiv_figures(db, source, fetch)
    except Exception:
        db.rollback()
        logger.exception("arxiv figure extraction failed for %s", source.id)
