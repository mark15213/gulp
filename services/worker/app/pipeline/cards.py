"""Card-generation stage: KnowledgePack -> CardsPayload -> Card rows.

Independent of digest (spec §③): reads the *current* pack (including manual
edits), never re-runs it. Replace semantics: a re-run replaces this source's
`origin=pack` drafts only — accepted/rejected and imported cards are kept.
`Source.cards_status` tracks this job: generating -> ready | failed.
"""

import logging
import uuid

from gulp_shared.contracts.cards import (
    MAX_CARDS_PER_PAYLOAD,
    CardDraft,
    CardsPayload,
)
from gulp_shared.llm import ModelConfig, complete_structured
from gulp_shared.llm.base import LLMProvider
from gulp_shared.models.card import Card, CardOrigin, CardStatus
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackStatus,
)
from gulp_shared.models.pack_block_message import PackBlockMessage
from gulp_shared.models.source import CardsStatus, Source
from gulp_shared.settings import settings
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.prompts.cards import build_cards_messages

logger = logging.getLogger("gulp.worker")


class CardGeneration(BaseModel):
    """The generation turn's output: a transient curriculum (the model's
    chain-of-thought, **not persisted**) plus the cards it yields. Only `cards`
    are kept — `curriculum` exists so the model reasons before emitting."""

    curriculum: str
    cards: list[CardDraft] = Field(min_length=1, max_length=MAX_CARDS_PER_PAYLOAD)


class CardsError(Exception):
    """A card-generation failure that should land cards_status in `failed`."""


def _render_block(block: PackBlock) -> str:
    data = block.data or {}
    if block.block_type is PackBlockType.prose:
        return str(data.get("content", ""))
    if block.block_type is PackBlockType.formula:
        return f"{data.get('latex', '')} — {data.get('explanation', '')}"
    if block.block_type is PackBlockType.table:
        headers = " | ".join(data.get("headers", []))
        rows = "\n".join(" | ".join(r) for r in data.get("rows", []))
        caption = data.get("caption") or ""
        return "\n".join(x for x in (caption, headers, rows) if x)
    if block.block_type is PackBlockType.figure:
        return f"{data.get('label', '')}: {data.get('explanation', '')}"
    if block.block_type is PackBlockType.list:
        return "\n".join(f"- {item}" for item in data.get("items", []))
    if block.block_type is PackBlockType.code:
        lang = data.get("language") or ""
        return f"```{lang}\n{data.get('content', '')}\n```"
    return ""


def render_pack_text(pack: KnowledgePack) -> str:
    # Header is extras-driven, so no dispatch on pack_type: paper packs carry
    # key_insight/core_contributions/references in extras, article packs don't.
    parts = [f"# {pack.title}"]
    if pack.summary:
        parts.append(pack.summary)
    extras = pack.extras or {}
    if extras.get("key_insight"):
        parts.append(f"Key insight: {extras['key_insight']}")
    if extras.get("core_contributions"):
        parts.append("Core contributions:")
        parts += [f"- {c}" for c in extras["core_contributions"]]
    for section in sorted(pack.sections, key=lambda s: s.position):
        parts.append(f"\n## {section.heading or ''}")
        parts += [
            _render_block(b) for b in sorted(section.blocks, key=lambda b: b.position)
        ]
    if extras.get("references"):
        parts.append("\nReferences:")
        parts += [
            f"- {r.get('citation', '')} — {r.get('why_interesting', '')}"
            for r in extras["references"]
        ]
    return "\n".join(parts)


def render_conversation(db: Session, pack: KnowledgePack) -> str:
    """The learner's per-block chat, grouped by block in reading order — a signal
    of what confused or interested them. Empty when there is no conversation."""
    block_ids = [b.id for s in pack.sections for b in s.blocks]
    if not block_ids:
        return ""
    messages = db.scalars(
        select(PackBlockMessage)
        .where(PackBlockMessage.block_id.in_(block_ids))
        .order_by(PackBlockMessage.created_at, PackBlockMessage.id)
    ).all()
    if not messages:
        return ""
    by_block: dict[uuid.UUID, list[PackBlockMessage]] = {}
    for m in messages:
        by_block.setdefault(m.block_id, []).append(m)
    parts: list[str] = []
    for section in sorted(pack.sections, key=lambda s: s.position):
        for block in sorted(section.blocks, key=lambda b: b.position):
            turns = by_block.get(block.id)
            if not turns:
                continue
            parts.append(f"[On: {_render_block(block)[:120]}]")
            parts += [f"{t.role.value}: {t.content}" for t in turns]
    return "\n".join(parts)


async def run_cards(
    pack_text: str,
    conversation_text: str = "",
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> CardGeneration:
    cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)
    system, messages = build_cards_messages(pack_text, conversation_text)
    return await complete_structured(
        response_model=CardGeneration,
        system=system,
        messages=messages,
        config=cfg,
        provider=provider,
    )


def persist_cards(db: Session, source: Source, payload: CardsPayload) -> list[Card]:
    stale = db.scalars(
        select(Card).where(
            Card.source_id == source.id,
            Card.origin == CardOrigin.pack,
            Card.status == CardStatus.draft,
        )
    ).all()
    for card in stale:
        db.delete(card)
    db.flush()
    rows = [
        Card(
            source_id=source.id,
            card_type=draft.card_type,
            prompt=draft.prompt,
            answer=draft.answer,
            explanation=draft.explanation,
            options=draft.options,
            origin=CardOrigin.pack,
        )
        for draft in payload.cards
    ]
    db.add_all(rows)
    db.flush()
    return rows


async def generate_cards_for_source(
    db: Session,
    source: Source,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> None:
    logger.info("generate_cards started source_id=%s", source.id)
    source.cards_status = CardsStatus.generating
    db.commit()
    try:
        pack = db.scalar(
            select(KnowledgePack).where(KnowledgePack.snapshot_id == source.id)
        )
        if pack is None or pack.status is not PackStatus.ready:
            raise CardsError("no ready pack to draft cards from")
        generation = await run_cards(
            render_pack_text(pack),
            render_conversation(db, pack),
            provider=provider,
            config=config,
        )
        persist_cards(db, source, CardsPayload(cards=generation.cards))
        source.cards_status = CardsStatus.ready
        db.commit()
        logger.info("generate_cards completed source_id=%s", source.id)
    except Exception:
        db.rollback()
        source.cards_status = CardsStatus.failed
        db.commit()
        logger.exception("generate_cards failed for %s", source.id)
