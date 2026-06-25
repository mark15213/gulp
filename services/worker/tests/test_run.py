from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.llm.base import Message, ModelConfig
from app.pipeline.run import process_source
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import KnowledgePack  # type: ignore[import-untyped]
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


class FakeProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def complete_json(self, *, system: str | None, messages: list[Message],
                            json_schema: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        return self.payload


_OK = {
    "summary": "s", "background": None, "confidence": 0.8,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
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

    async def _no_fetch(url: str) -> str:  # notes never fetch
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

    async def _fetch(url: str) -> str:
        return ("<html><head><title>A</title></head><body><article>"
                "<h1>A</h1><p>Attention weighs tokens by relevance across the input.</p>"
                "</article></body></html>")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert snap.media_type == MediaType.article  # precise type set
    assert snap.content_body and "relevance" in snap.content_body  # extracted body stored


async def test_failure_sets_needs_attention() -> None:
    s = _session()
    snap = _note(s)

    class Boom:
        async def complete_json(self, **kw: Any) -> dict[str, Any]:
            raise RuntimeError("llm down")

    await process_source(s, snap, provider=Boom())
    assert snap.status == SnapshotStatus.needs_attention
