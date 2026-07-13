import asyncio
import uuid
from typing import Any

import pytest
from app.deps import get_db
from app.main import app
from app.services.chat import MarkerFilter, answer_question, answer_stream, list_messages
from fastapi.testclient import TestClient
from gulp_shared.llm import ChatMessage
from gulp_shared.llm import catalog as llm_catalog
from gulp_shared.llm.base import DoneEvent, TextDelta
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.pack_message import ChatRole
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID
from gulp_shared.settings import settings


class FakeProvider:
    def __init__(self) -> None:
        self.last_system: str | None = None
        self.last_messages: list[ChatMessage] = []

    async def complete_json(self, *, system, messages, json_schema, config) -> dict[str, Any]:
        self.last_system = system
        self.last_messages = messages
        return {"answer": "Because the source says so."}


def _pack(db) -> dict:  # type: ignore[no-untyped-def]
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="T",
        status=SnapshotStatus.ready,
        content_body="The source body text.",
    )
    db.add(snap)
    db.flush()
    pack = KnowledgePack(
        snapshot_id=snap.id,
        title="BERT",
        summary="A summary.",
        pack_type=PackType.paper,
        extras={"key_insight": "Change the objective."},
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="Method", position=0)
    db.add(sec)
    db.flush()
    block = PackBlock(
        section_id=sec.id,
        block_type=PackBlockType.prose,
        data={"content": "Masked language modeling."},
        position=0,
    )
    db.add(block)
    db.commit()
    return {"snap": snap.id, "block": block.id}


def test_answer_grounds_and_persists_with_attachment(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeProvider()
    msg = asyncio.run(
        answer_question(db, ids["snap"], "Why masking?", [ids["block"]], provider=fake)
    )
    assert msg.role is ChatRole.assistant
    assert msg.content == "Because the source says so."
    history = list_messages(db, ids["snap"])
    assert [m.role for m in history] == [ChatRole.user, ChatRole.assistant]
    assert history[0].content == "Why masking?"
    assert [str(r) for r in history[0].block_refs] == [str(ids["block"])]
    # grounding: source + pack context + the ATTACHED block text
    assert "The source body text." in (fake.last_system or "")
    assert "BERT" in (fake.last_system or "")
    assert "Masked language modeling." in (fake.last_system or "")


def test_answer_without_attachments_is_general(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeProvider()
    asyncio.run(answer_question(db, ids["snap"], "What is this about?", provider=fake))
    assert "The source body text." in (fake.last_system or "")


@pytest.fixture
def client(db, monkeypatch):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    spec = llm_catalog.PROVIDERS["anthropic"]
    fake_spec = llm_catalog.ProviderSpec(
        name=spec.name,
        adapter=FakeProvider(),
        base_url=spec.base_url,
        capabilities=spec.capabilities,
        models=spec.models,
    )
    monkeypatch.setitem(llm_catalog.PROVIDERS, "anthropic", fake_spec)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")  # dev fallback path
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_post_without_credentials_maps_to_409(db, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    app.dependency_overrides[get_db] = lambda: db
    ids = _pack(db)
    try:
        c = TestClient(app)
        r = c.post(f"/snapshots/{ids['snap']}/messages", json={"content": "Q"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 409
    assert r.json()["detail"] == "llm_not_configured"


def test_post_then_get_messages(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/messages",
        json={"content": "Why masking?", "block_refs": [str(ids["block"])]},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "assistant"
    g = client.get(f"/snapshots/{ids['snap']}/messages")
    assert [m["role"] for m in g.json()] == ["user", "assistant"]
    assert g.json()[0]["block_refs"] == [str(ids["block"])]


def test_messages_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(
        owner_id=uuid.uuid4(),
        kind=SourceKind.snapshot,
        title="F",
        status=SnapshotStatus.ready,
    )
    db.add(foreign)
    db.commit()
    r = client.get(f"/snapshots/{foreign.id}/messages")
    assert r.status_code == 404


class FakeStreamProvider:
    def __init__(self, *chunks: str) -> None:
        self.chunks = chunks
        self.last_system: str | None = None

    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        raise AssertionError("streaming path must not call complete_json")

    async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
        self.last_system = system
        for c in self.chunks:
            yield TextDelta(text=c)
        yield DoneEvent(stop_reason="stop")


async def _collect(agen) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    return [e async for e in agen]


def test_marker_filter_strips_split_markers() -> None:
    bid = "11111111-1111-1111-1111-111111111111"
    mf = MarkerFilter()
    out = mf.feed("Attention is [[bl") + mf.feed(f"ock:{bid}]] key.") + mf.flush()
    assert out == "Attention is  key."
    assert mf.text == "Attention is  key."
    assert [str(r) for r in mf.refs] == [bid]


def test_marker_filter_passes_plain_double_brackets() -> None:
    mf = MarkerFilter()
    out = mf.feed("a [[note]] b") + mf.flush()
    assert out == "a [[note]] b" and mf.refs == []


def test_answer_stream_persists_thread_with_refs(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("The answer ", f"[[block:{ids['block']}]]", "is 42.")
    events = asyncio.run(_collect(answer_stream(db, ids["snap"], "Why?", provider=fake)))
    assert events[-1]["type"] == "done"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "The answer is 42."
    msgs = list_messages(db, ids["snap"])
    assert [m.role.value for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "The answer is 42."
    assert msgs[1].block_refs == [str(ids["block"])]
    assert events[-1]["message"]["content"] == "The answer is 42."


def test_answer_stream_drops_unknown_block_refs(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("Hi [[block:99999999-9999-9999-9999-999999999999]] there.")
    asyncio.run(_collect(answer_stream(db, ids["snap"], "Q", provider=fake)))
    msgs = list_messages(db, ids["snap"])
    assert msgs[1].block_refs == []


def test_answer_stream_system_lists_citable_blocks(db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    fake = FakeStreamProvider("ok")
    asyncio.run(_collect(answer_stream(db, ids["snap"], "Q", provider=fake)))
    assert str(ids["block"]) in (fake.last_system or "")
    assert "[[block:" in (fake.last_system or "")  # citation instruction present
