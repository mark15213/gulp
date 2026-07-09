"""Per-block grounded chat: assemble context, call the LLM, persist the thread."""

import uuid

from gulp_shared.llm import LLMProvider, ModelConfig, complete_structured
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
from gulp_shared.models.source import Source
from gulp_shared.settings import settings
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.pack import load_block_scoped

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


def list_messages(
    db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID
) -> list[PackBlockMessage]:
    load_block_scoped(db, snapshot_id, block_id)  # raises LookupError if not owned/in snapshot
    return list(
        db.scalars(
            select(PackBlockMessage)
            .where(
                PackBlockMessage.block_id == block_id,
                PackBlockMessage.deleted_at.is_(None),
            )
            .order_by(PackBlockMessage.created_at)
        )
    )


def _grounding_system(db: Session, snapshot_id: uuid.UUID, block: PackBlock) -> str:
    section = db.get(PackSection, block.section_id)
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    source = db.scalar(select(Source).where(Source.id == snapshot_id))
    body = (source.content_body or "") if source else ""
    key_insight = (pack.extras or {}).get("key_insight", "") if pack else ""
    return (
        "You are helping the reader understand one block of a knowledge pack. "
        "Answer the question grounded in the provided source and block; if the "
        "source does not cover it, say so plainly.\n"
        f"Pack title: {pack.title if pack else ''}\n"
        f"Key insight: {key_insight}\n"
        f"Section: {section.heading if section else ''}\n"
        f"Block ({block.block_type.value}): {_block_text(block)}\n"
        f"Source excerpt:\n{body[:_MAX_SOURCE_CHARS]}"
    )


async def answer_question(
    db: Session,
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    question: str,
    *,
    provider: LLMProvider | None = None,
) -> PackBlockMessage:
    block = load_block_scoped(db, snapshot_id, block_id)

    user_msg = PackBlockMessage(block_id=block_id, role=ChatRole.user, content=question)
    db.add(user_msg)
    db.flush()

    history = list_messages(db, snapshot_id, block_id)
    messages = [{"role": m.role.value, "content": m.content} for m in history]
    system = _grounding_system(db, snapshot_id, block)

    result = await complete_structured(
        response_model=ChatAnswer,
        messages=messages,
        system=system,
        config=ModelConfig(provider=settings.llm_provider, model=settings.llm_model),
        provider=provider,
    )

    assistant_msg = PackBlockMessage(
        block_id=block_id, role=ChatRole.assistant, content=result.answer
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg
