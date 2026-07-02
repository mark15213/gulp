"""Card-generation stage: KnowledgePack -> CardsPayload -> Card rows.

Independent of digest (spec §③): reads the *current* pack (including manual
edits), never re-runs it. Replace semantics: a re-run replaces this source's
`origin=pack` drafts only — accepted/rejected and imported cards are kept.
`Source.cards_status` tracks this job: generating -> ready | failed.
"""

import logging

from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.llm import ModelConfig, complete_structured
from gulp_shared.llm.base import LLMProvider
from gulp_shared.models.card import Card, CardOrigin, CardStatus
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackStatus,
)
from gulp_shared.models.source import CardsStatus, Source
from gulp_shared.settings import settings
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.prompts.cards import build_cards_messages

logger = logging.getLogger("gulp.worker")


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
    return ""


def render_pack_text(pack: KnowledgePack) -> str:
    parts = [f"# {pack.title}", f"Key insight: {pack.key_insight}", "Core contributions:"]
    parts += [f"- {c}" for c in pack.core_contributions or []]
    for section in sorted(pack.sections, key=lambda s: s.position):
        parts.append(f"\n## {section.heading or ''}")
        parts += [
            _render_block(b) for b in sorted(section.blocks, key=lambda b: b.position)
        ]
    if pack.references:
        parts.append("\nReferences:")
        parts += [
            f"- {r.get('citation', '')} — {r.get('why_interesting', '')}"
            for r in pack.references
        ]
    return "\n".join(parts)


async def run_cards(
    pack_text: str,
    *,
    provider: LLMProvider | None = None,
    config: ModelConfig | None = None,
) -> CardsPayload:
    cfg = config or ModelConfig(provider=settings.llm_provider, model=settings.llm_model)
    system, messages = build_cards_messages(pack_text)
    return await complete_structured(
        response_model=CardsPayload,
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
    source.cards_status = CardsStatus.generating
    db.commit()
    try:
        pack = db.scalar(
            select(KnowledgePack).where(KnowledgePack.snapshot_id == source.id)
        )
        if pack is None or pack.status is not PackStatus.ready:
            raise CardsError("no ready pack to draft cards from")
        payload = await run_cards(render_pack_text(pack), provider=provider, config=config)
        persist_cards(db, source, payload)
        source.cards_status = CardsStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.cards_status = CardsStatus.failed
        db.commit()
        logger.exception("generate_cards failed for %s", source.id)
