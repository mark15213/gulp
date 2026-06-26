from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.metadata import run_resolve_metadata
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind  # type: ignore[import-untyped]
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _pdf_fetch():  # type: ignore[no-untyped-def]
    data = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()

    async def _fetch(url: str) -> FetchedDoc:
        return FetchedDoc(content=data, content_type="application/pdf")

    return _fetch


async def test_resolve_sets_real_title_and_pdf_type_over_host_placeholder() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="arxiv.org",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/x")
    s.add(snap); s.flush()
    await run_resolve_metadata(s, snap, fetch=_pdf_fetch())
    assert snap.title == "The Spacing Effect"
    assert snap.media_type == MediaType.pdf


async def test_resolve_keeps_a_user_supplied_title() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="My own title",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/x")
    s.add(snap); s.flush()
    await run_resolve_metadata(s, snap, fetch=_pdf_fetch())
    assert snap.title == "My own title"  # not the host placeholder -> untouched
    assert snap.media_type == MediaType.pdf  # type still refined


async def test_resolve_uses_arxiv_abstract_title_for_a_pdf_link() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="arxiv.org",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/1706.03762")
    s.add(snap); s.flush()

    pdf = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()
    abs_html = ('<html><head><meta name="citation_title" '
                'content="Attention Is All You Need"></head><body>x</body></html>')

    async def _fetch(url: str) -> FetchedDoc:
        if "/abs/" in url:
            return FetchedDoc(content=abs_html.encode(), content_type="text/html")
        return FetchedDoc(content=pdf, content_type="application/pdf")

    await run_resolve_metadata(s, snap, fetch=_fetch)
    assert snap.title == "Attention Is All You Need"  # from the abstract page, not the PDF first line
    assert snap.media_type == MediaType.pdf            # still from the real (PDF) fetch
