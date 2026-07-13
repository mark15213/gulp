"""Snapshot-scoped article chat: assemble context (+ attached blocks), call the
LLM, persist the thread (spec 2026-07-10 reader redesign)."""

import uuid

from gulp_shared.llm import ChatMessage, LLMProvider, ModelConfig, complete_structured
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_message import ChatRole, PackMessage
from gulp_shared.models.source import Source
from gulp_shared.settings import settings
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

_MAX_SOURCE_CHARS = 6000


class ChatAnswer(BaseModel):
    answer: str


def _block_text(block: PackBlock) -> str:
    d = block.data or {}
    t = block.block_type.value
    if t == "prose":
        return str(d.get("content", ""))
    if t == "formula":
        return f"{d.get('latex', '')} — {d.get('explanation', '')}"
    if t == "table":
        return f"headers={d.get('headers')}, rows={d.get('rows')}"
    if t == "figure":
        return f"{d.get('label', '')}: {d.get('explanation', '')}"
    if t == "list":
        return "; ".join(str(x) for x in d.get("items", []))
    return ""


def list_messages(db: Session, snapshot_id: uuid.UUID) -> list[PackMessage]:
    return list(
        db.scalars(
            select(PackMessage)
            .where(PackMessage.snapshot_id == snapshot_id, PackMessage.deleted_at.is_(None))
            .order_by(PackMessage.created_at)
        )
    )


def _attached_blocks(
    db: Session, snapshot_id: uuid.UUID, refs: list[uuid.UUID]
) -> list[PackBlock]:
    if not refs:
        return []
    return list(
        db.scalars(
            select(PackBlock)
            .join(PackSection, PackBlock.section_id == PackSection.id)
            .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
            .where(
                PackBlock.id.in_(refs),
                PackBlock.deleted_at.is_(None),
                KnowledgePack.snapshot_id == snapshot_id,
                KnowledgePack.deleted_at.is_(None),
            )
        )
    )


def _grounding_system(
    db: Session, snapshot_id: uuid.UUID, attached: list[PackBlock]
) -> str:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    source = db.get(Source, snapshot_id)
    body = (source.content_body or "") if source else ""
    key_insight = (pack.extras or {}).get("key_insight", "") if pack else ""
    parts = [
        "You are helping the reader understand and discuss a knowledge pack (a "
        "digested article/paper). Answer grounded in the provided source and pack; "
        "if the source does not cover it, say so plainly.",
        f"Pack title: {pack.title if pack else ''}",
        f"Summary: {pack.summary if pack else ''}",
        f"Key insight: {key_insight}",
    ]
    if attached:
        blocks_txt = "\n".join(f"- ({b.block_type.value}) {_block_text(b)}" for b in attached)
        parts.append("The reader is asking specifically about these blocks:\n" + blocks_txt)
    parts.append(f"Source excerpt:\n{body[:_MAX_SOURCE_CHARS]}")
    return "\n".join(parts)


async def answer_question(
    db: Session,
    snapshot_id: uuid.UUID,
    question: str,
    block_refs: list[uuid.UUID] | None = None,
    *,
    provider: LLMProvider | None = None,
) -> PackMessage:
    refs = [uuid.UUID(str(r)) for r in (block_refs or [])]
    attached = _attached_blocks(db, snapshot_id, refs)

    user_msg = PackMessage(
        snapshot_id=snapshot_id,
        role=ChatRole.user,
        content=question,
        block_refs=[str(r) for r in refs],
    )
    db.add(user_msg)
    db.flush()

    history = list_messages(db, snapshot_id)
    messages = [
        ChatMessage(role="user" if m.role is ChatRole.user else "assistant", content=m.content)
        for m in history
    ]
    system = _grounding_system(db, snapshot_id, attached)

    result = await complete_structured(
        response_model=ChatAnswer,
        messages=messages,
        system=system,
        config=ModelConfig(provider=settings.llm_provider, model=settings.llm_model),
        provider=provider,
    )

    assistant_msg = PackMessage(
        snapshot_id=snapshot_id, role=ChatRole.assistant, content=result.answer, block_refs=[]
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg
