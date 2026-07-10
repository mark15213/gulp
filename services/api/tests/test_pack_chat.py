import asyncio
import uuid
from typing import Any

import pytest
from app.deps import get_db
from app.main import app
from app.services.chat import answer_question, list_messages
from fastapi.testclient import TestClient
from gulp_shared.llm import AnthropicProvider, register_provider
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


class FakeProvider:
    def __init__(self) -> None:
        self.last_system: str | None = None
        self.last_messages: list[dict[str, str]] = []

    async def complete_json(self, *, system, messages, json_schema, config) -> dict[str, Any]:
        self.last_system = system
        self.last_messages = messages
        return {"answer": "Because the source says so."}


def _pack(db) -> dict:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, content_body="The source body text.")
    db.add(snap); db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", summary="A summary.",
                         pack_type=PackType.paper, extras={"key_insight": "Change the objective."},
                         status=PackStatus.ready)
    db.add(pack); db.flush()
    sec = PackSection(pack_id=pack.id, heading="Method", position=0)
    db.add(sec); db.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                      data={"content": "Masked language modeling."}, position=0)
    db.add(block); db.commit()
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
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    register_provider("anthropic", FakeProvider())
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    register_provider("anthropic", AnthropicProvider())


def test_post_then_get_messages(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack(db)
    r = client.post(f"/snapshots/{ids['snap']}/messages",
                    json={"content": "Why masking?", "block_refs": [str(ids["block"])]})
    assert r.status_code == 201
    assert r.json()["role"] == "assistant"
    g = client.get(f"/snapshots/{ids['snap']}/messages")
    assert [m["role"] for m in g.json()] == ["user", "assistant"]
    assert g.json()[0]["block_refs"] == [str(ids["block"])]


def test_messages_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="F",
                     status=SnapshotStatus.ready)
    db.add(foreign); db.commit()
    r = client.get(f"/snapshots/{foreign.id}/messages")
    assert r.status_code == 404
