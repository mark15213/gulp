"""Card generation stage: render pack -> LLM turn -> persist with replace semantics."""

from typing import Any

import gulp_shared.models  # noqa: F401
from app.pipeline.cards import (
    CardGeneration,
    generate_cards_for_source,
    persist_cards,
    render_conversation,
    render_pack_text,
    run_cards,
)
from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.db import Base
from gulp_shared.llm.base import Message, ModelConfig
from gulp_shared.models.card import (
    Card,
    CardOrigin,
    CardStatus,
    CardType,
)
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.pack_message import ChatRole, PackMessage
from gulp_shared.models.source import (
    CardsStatus,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.last_body: str | None = None

    async def complete_json(
        self,
        *,
        system: str | None,
        messages: list[Message],
        json_schema: dict[str, Any],
        config: ModelConfig,
    ) -> dict[str, Any]:
        self.last_body = messages[0]["content"]
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return self.payload


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snapshot(s, *, status=SnapshotStatus.ready):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T", status=status
    )
    s.add(snap)
    s.flush()
    return snap


def _pack(s, snap, *, status=PackStatus.ready):  # type: ignore[no-untyped-def]
    pack = KnowledgePack(
        snapshot_id=snap.id,
        title="BERT",
        pack_type=PackType.paper,
        extras={
            "key_insight": "Bidirectional pretraining transfers.",
            "core_contributions": ["MLM objective", "NSP task"],
            "references": [{"citation": "ELMo", "why_interesting": "context"}],
        },
        status=status,
    )
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="Approach", position=0)
    s.add(sec)
    s.flush()
    s.add_all(
        [
            PackBlock(
                section_id=sec.id,
                block_type=PackBlockType.prose,
                data={"content": "Masked language modeling."},
                position=0,
            ),
            PackBlock(
                section_id=sec.id,
                block_type=PackBlockType.formula,
                data={"latex": "L = L_{mlm}", "explanation": "the loss"},
                position=1,
            ),
            PackBlock(
                section_id=sec.id,
                block_type=PackBlockType.list,
                data={"items": ["12 layers", "110M params"], "ordered": False},
                position=2,
            ),
        ]
    )
    s.flush()
    return pack


_PAYLOAD = {
    "curriculum": "Master the MLM objective and layer count; the learner asked about layers.",
    "cards": [
        {
            "card_type": "flashcard",
            "prompt": "What objective does BERT use?",
            "answer": "Masked language modeling",
            "explanation": "Stated in Approach.",
        },
        {
            "card_type": "mcq",
            "prompt": "How many layers?",
            "answer": "12",
            "options": ["6", "12", "24"],
        },
    ]
}


def test_render_pack_text_covers_root_fields_and_blocks():
    s = _session()
    snap = _snapshot(s)
    pack = _pack(s, snap)
    text = render_pack_text(pack)
    assert "BERT" in text
    assert "Bidirectional pretraining transfers." in text
    assert "MLM objective" in text
    assert "Approach" in text
    assert "Masked language modeling." in text
    assert "L = L_{mlm}" in text
    assert "110M params" in text


async def test_run_cards_returns_generation_with_curriculum_and_cards():
    prov = FakeProvider(_PAYLOAD)
    out = await run_cards("PACK TEXT", provider=prov)
    assert isinstance(out, CardGeneration)
    assert out.curriculum
    assert len(out.cards) == 2
    assert prov.last_body is not None and "PACK TEXT" in prov.last_body


def test_render_conversation_includes_turns_and_attachment():
    s = _session()
    snap = _snapshot(s)
    pack = _pack(s, snap)
    block = pack.sections[0].blocks[0]
    s.add_all(
        [
            PackMessage(
                snapshot_id=snap.id,
                role=ChatRole.user,
                content="Why masked LM?",
                block_refs=[str(block.id)],
            ),
            PackMessage(
                snapshot_id=snap.id,
                role=ChatRole.assistant,
                content="Because bidirectional context.",
                block_refs=[],
            ),
        ]
    )
    s.flush()
    text = render_conversation(s, pack)
    assert "Why masked LM?" in text
    assert "Because bidirectional context." in text
    assert "[On:" in text  # the attached block is annotated


def test_render_conversation_empty_when_no_messages():
    s = _session()
    snap = _snapshot(s)
    pack = _pack(s, snap)
    assert render_conversation(s, pack) == ""


async def test_generate_feeds_conversation_into_prompt():
    s = _session()
    snap = _snapshot(s)
    pack = _pack(s, snap)
    s.add(
        PackMessage(
            snapshot_id=snap.id,
            role=ChatRole.user,
            content="Why masked LM?",
            block_refs=[str(pack.sections[0].blocks[0].id)],
        )
    )
    s.commit()
    prov = FakeProvider(_PAYLOAD)
    await generate_cards_for_source(s, snap, provider=prov)
    assert prov.last_body is not None and "Why masked LM?" in prov.last_body


def test_persist_cards_replaces_only_pack_origin_drafts():
    s = _session()
    snap = _snapshot(s)
    keep_accepted = Card(
        source_id=snap.id, card_type=CardType.flashcard, prompt="old accepted",
        answer="a", origin=CardOrigin.pack, status=CardStatus.accepted,
    )
    keep_imported = Card(
        source_id=snap.id, card_type=CardType.flashcard, prompt="imported draft",
        answer="a", origin=CardOrigin.imported,
    )
    stale_draft = Card(
        source_id=snap.id, card_type=CardType.flashcard, prompt="old draft",
        answer="a", origin=CardOrigin.pack,
    )
    s.add_all([keep_accepted, keep_imported, stale_draft])
    s.commit()

    persist_cards(s, snap, CardsPayload.model_validate({"cards": _PAYLOAD["cards"]}))
    s.commit()

    prompts = set(s.scalars(select(Card.prompt).where(Card.source_id == snap.id)))
    assert "old draft" not in prompts
    assert {"old accepted", "imported draft"} <= prompts
    new = s.scalars(
        select(Card).where(Card.prompt == "What objective does BERT use?")
    ).one()
    assert new.origin == CardOrigin.pack and new.status == CardStatus.draft


async def test_generate_cards_success_sets_ready():
    s = _session()
    snap = _snapshot(s)
    _pack(s, snap)
    s.commit()
    await generate_cards_for_source(s, snap, provider=FakeProvider(_PAYLOAD))
    assert snap.cards_status == CardsStatus.ready
    cards = s.scalars(select(Card).where(Card.source_id == snap.id)).all()
    assert len(cards) == 2


async def test_generate_cards_failure_sets_failed():
    s = _session()
    snap = _snapshot(s)
    _pack(s, snap)
    s.commit()
    await generate_cards_for_source(s, snap, provider=FakeProvider(error=RuntimeError("boom")))
    assert snap.cards_status == CardsStatus.failed
    assert s.scalars(select(Card).where(Card.source_id == snap.id)).all() == []


async def test_generate_cards_without_ready_pack_sets_failed():
    s = _session()
    snap = _snapshot(s)  # no pack at all
    s.commit()
    await generate_cards_for_source(s, snap, provider=FakeProvider(_PAYLOAD))
    assert snap.cards_status == CardsStatus.failed
