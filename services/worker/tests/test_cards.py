"""Card generation stage: render pack -> LLM turn -> persist with replace semantics."""

from typing import Any

import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from app.pipeline.cards import (
    generate_cards_for_source,
    persist_cards,
    render_pack_text,
    run_cards,
)
from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.db import Base  # type: ignore[import-untyped]
from gulp_shared.llm.base import Message, ModelConfig  # type: ignore[import-untyped]
from gulp_shared.models.card import (  # type: ignore[import-untyped]
    Card,
    CardOrigin,
    CardStatus,
    CardType,
)
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    CardsStatus,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]
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
        key_insight="Bidirectional pretraining transfers.",
        core_contributions=["MLM objective", "NSP task"],
        references=[{"citation": "ELMo", "why_interesting": "context"}],
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
    "cards": [
        {
            "card_type": "short_answer",
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


async def test_run_cards_returns_validated_payload():
    prov = FakeProvider(_PAYLOAD)
    out = await run_cards("PACK TEXT", provider=prov)
    assert isinstance(out, CardsPayload)
    assert len(out.cards) == 2
    assert prov.last_body is not None and "PACK TEXT" in prov.last_body


def test_persist_cards_replaces_only_pack_origin_drafts():
    s = _session()
    snap = _snapshot(s)
    keep_accepted = Card(
        source_id=snap.id, card_type=CardType.short_answer, prompt="old accepted",
        answer="a", origin=CardOrigin.pack, status=CardStatus.accepted,
    )
    keep_imported = Card(
        source_id=snap.id, card_type=CardType.short_answer, prompt="imported draft",
        answer="a", origin=CardOrigin.imported,
    )
    stale_draft = Card(
        source_id=snap.id, card_type=CardType.short_answer, prompt="old draft",
        answer="a", origin=CardOrigin.pack,
    )
    s.add_all([keep_accepted, keep_imported, stale_draft])
    s.commit()

    persist_cards(s, snap, CardsPayload.model_validate(_PAYLOAD))
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
