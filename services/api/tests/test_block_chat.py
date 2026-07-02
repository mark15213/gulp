import asyncio
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db
from app.main import app
from app.services.chat import answer_question, list_messages
from gulp_shared.llm import register_provider
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.pack_block_message import ChatRole
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


class FakeProvider:
    """Records the grounding it received; returns a fixed structured answer."""

    def __init__(self) -> None:
        self.last_system: str | None = None
        self.last_messages: list[dict[str, str]] = []

    async def complete_json(self, *, system, messages, json_schema, config) -> dict[str, Any]:
        self.last_system = system
        self.last_messages = messages
        return {"answer": "Because the source says so."}


def _block(db) -> dict:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, content_body="The source body text.")
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", key_insight="Change the objective.",
                         core_contributions=[], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="Method", position=0)
    db.add(sec)
    db.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                      data={"content": "Masked language modeling."}, position=0)
    db.add(block)
    db.commit()
    return {"snap": snap.id, "block": block.id}


def test_answer_question_persists_turns_and_grounds(db) -> None:  # type: ignore[no-untyped-def]
    ids = _block(db)
    fake = FakeProvider()
    msg = asyncio.run(answer_question(db, ids["snap"], ids["block"], "Why masking?", provider=fake))
    assert msg.role is ChatRole.assistant
    assert msg.content == "Because the source says so."
    # both turns persisted, oldest first
    history = list_messages(db, ids["snap"], ids["block"])
    assert [m.role for m in history] == [ChatRole.user, ChatRole.assistant]
    assert history[0].content == "Why masking?"
    # grounding carried the source body + pack context + the block text
    assert "The source body text." in (fake.last_system or "")
    assert "BERT" in (fake.last_system or "")
    assert "Masked language modeling." in (fake.last_system or "")
    # the user question is the last chat message sent to the model
    assert fake.last_messages[-1] == {"role": "user", "content": "Why masking?"}


def test_list_messages_404_for_block_not_in_snapshot(db) -> None:  # type: ignore[no-untyped-def]
    ids = _block(db)
    with pytest.raises(LookupError):
        list_messages(db, ids["snap"], uuid.uuid4())


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    register_provider("anthropic", FakeProvider())  # no real API call in tests
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_post_then_get_messages(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _block(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/blocks/{ids['block']}/messages",
        json={"content": "Why masking?"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "assistant"
    assert r.json()["content"] == "Because the source says so."

    g = client.get(f"/snapshots/{ids['snap']}/blocks/{ids['block']}/messages")
    assert g.status_code == 200
    body = g.json()
    assert [m["role"] for m in body] == ["user", "assistant"]
    assert body[0]["content"] == "Why masking?"


def test_messages_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="F",
                     status=SnapshotStatus.ready)
    db.add(foreign)
    db.commit()
    r = client.get(f"/snapshots/{foreign.id}/blocks/{uuid.uuid4()}/messages")
    assert r.status_code == 404
