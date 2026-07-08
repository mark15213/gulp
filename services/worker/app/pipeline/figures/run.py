# services/worker/app/pipeline/figures/run.py
"""Best-effort arXiv figure extraction step (spec §4). Callable in isolation with
an injected fetch; the pipeline provides the real one."""

from collections.abc import Awaitable, Callable

from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.adapters.arxiv import arxiv_eprint_url, is_arxiv
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.extract import extract_figures
from app.pipeline.figures.match import link_figures
from app.pipeline.figures.persist import persist_figures

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


async def extract_arxiv_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    url = source.origin_url or ""
    if not is_arxiv(url):
        return
    eprint = arxiv_eprint_url(url)
    if eprint is None:
        return
    doc = await fetch(eprint)
    figures = extract_figures(doc.content)
    if figures:
        persist_figures(db, source, figures)
        db.commit()


async def link_imported_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    """Post-import step: make sure figures exist (arXiv fetch — no LLM), then
    auto-link the pack's figure blocks to them by figure number."""
    have = db.scalar(
        select(SourceFigure.id).where(SourceFigure.source_id == source.id)
    )
    if have is None:
        await extract_arxiv_figures(db, source, fetch)
    if link_figures(db, source):
        db.commit()
