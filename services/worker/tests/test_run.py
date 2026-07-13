from pathlib import Path
from typing import Any

import gulp_shared.models  # noqa: F401
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.run import process_source
from gulp_shared.db import Base
from gulp_shared.llm.base import ChatMessage, ModelConfig
from gulp_shared.models.knowledge_pack import KnowledgePack, PackType
from gulp_shared.models.source import (
    MediaType,
    SnapshotStatus,
    Source,
    SourceGenre,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def complete_json(self, *, system: str | None, messages: list[ChatMessage],
                            json_schema: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        return self.payload


_OK = {
    "title": "T",
    "core_contributions": ["c"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _note(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="My note body.")
    s.add(snap)
    s.flush()
    return snap


async def test_note_pipeline_ends_ready_with_a_pack() -> None:
    s = _session()
    snap = _note(s)

    async def _no_fetch(url: str) -> FetchedDoc:  # notes never fetch
        raise AssertionError("note path must not fetch")

    await process_source(s, snap, fetch=_no_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)) is not None


async def test_link_pipeline_fetches_then_digests() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="L",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/a")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><head><title>A</title></head><body><article>"
                "<h1>A</h1><p>Attention weighs tokens by relevance across the input.</p>"
                "</article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html; charset=utf-8")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert snap.media_type == MediaType.article  # precise type set
    assert snap.content_body and "relevance" in snap.content_body  # extracted body stored


async def test_processing_detects_genre_when_unset() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="L",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://blog.example/post")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = "<html><body><article><p>Some post body text.</p></article></body></html>"
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))
    assert snap.genre == SourceGenre.article


async def test_processing_keeps_user_corrected_genre() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="L",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://blog.example/post", genre=SourceGenre.paper)
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><body><article><p>Actually a paper hosted on a blog.</p>"
                "</article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))
    assert snap.genre == SourceGenre.paper  # correction survives re-processing


class ExplodingProvider:
    """Any LLM call is a test failure — non-paper genres must be LLM-free."""

    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        raise AssertionError("LLM must not be called for this genre")


async def test_article_source_builds_preserve_pack_without_llm() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="L",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://blog.example/harness")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><head><title>Harness</title></head><body><article><h1>Harness</h1>"
                "<p>Original prose that must survive verbatim.</p></article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=ExplodingProvider())

    assert snap.status == SnapshotStatus.ready
    pack = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert pack is not None and pack.pack_type == PackType.article
    blocks = [b for sec in pack.sections for b in sec.blocks]
    assert any("survive verbatim" in (b.data or {}).get("content", "") for b in blocks)


async def test_arxiv_source_uses_paper_strategy() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="P",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/abs/2607.00123")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><body><article><p>Abstract of a serious paper.</p>"
                "</article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    pack = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert pack is not None and pack.pack_type == PackType.paper
    assert pack.extras.get("key_insight") == "k"


async def test_note_source_builds_preserve_pack() -> None:
    s = _session()
    snap = _note(s)
    await process_source(s, snap, provider=ExplodingProvider())
    assert snap.status == SnapshotStatus.ready
    pack = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert pack is not None and pack.pack_type == PackType.article


async def test_failure_sets_needs_attention() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    # paper genre: the digest is the LLM path, so an LLM failure must surface
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="P",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/abs/2607.00999")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = "<html><body><article><p>Paper body.</p></article></body></html>"
        return FetchedDoc(content=html.encode(), content_type="text/html")

    class Boom:
        async def complete_json(self, **kw: Any) -> dict[str, Any]:
            raise RuntimeError("llm down")

    await process_source(s, snap, fetch=_fetch, provider=Boom())
    assert snap.status == SnapshotStatus.needs_attention


async def test_pdf_link_routes_through_pdf_adapter() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="x.example",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/p.pdf")
    s.add(snap)
    s.flush()
    pdf_bytes = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()

    async def _fetch(url: str) -> FetchedDoc:
        return FetchedDoc(content=pdf_bytes, content_type="application/pdf")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert snap.media_type == MediaType.pdf
    assert "Distributed practice" in (snap.content_body or "")


async def test_link_pipeline_writes_real_title_over_host_placeholder() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="x.example",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/a")
    s.add(snap)
    s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><head><title>Real Title</title></head><body><article>"
                "<p>Body text here about relevance.</p></article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))
    assert snap.title == "Real Title"  # host placeholder replaced by the extracted title
