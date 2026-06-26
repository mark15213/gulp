"""resolve_metadata — fetch a link and write its real title + media type onto
the Source so the inbox stops showing the bare host. No AI; non-fatal on error.
"""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.pipeline.adapters.arxiv import arxiv_title
from app.pipeline.adapters.fetch import FetchedDoc, fetch_document
from app.pipeline.run import normdoc_from_fetched
from gulp_shared.models.source import MediaType, Source  # type: ignore[import-untyped]
from gulp_shared.urls import host_of  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


async def run_resolve_metadata(db: Session, source: Source, *, fetch: FetchFn = fetch_document) -> None:
    if not source.origin_url:
        return
    try:
        doc = await fetch(source.origin_url)
        nd = normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)
        source.media_type = MediaType(nd.media_type)
        title = (await arxiv_title(source.origin_url, fetch=fetch)) or nd.title
        if source.title == host_of(source.origin_url) and title and title != source.title:
            source.title = title
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("resolve_metadata failed for %s", source.id)
