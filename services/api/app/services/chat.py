"""Snapshot-scoped article chat: assemble context (+ attached blocks), stream
the LLM answer with inline [[block:ID]] citations, persist the thread
(spec 2026-07-13 MaaS layer §5.2)."""

import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from gulp_shared.llm import (
    ChatMessage,
    LLMProvider,
    ModelConfig,
    get_spec,
    resolve_model_config,
)
from gulp_shared.llm.base import (
    LLMAuthError,
    LLMError,
    LLMNotConfiguredError,
    LLMRateLimitError,
    TextDelta,
)
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_message import ChatRole, PackMessage
from gulp_shared.models.source import Source
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

_MAX_PACK_CONTEXT_CHARS = 24_000
_MAX_SOURCE_CHARS = 12_000
_MAX_HISTORY_MESSAGES = 24


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
    if t == "code":
        language = str(d.get("language") or "code")
        return f"```{language}\n{d.get('content', '')}\n```"
    return ""


def list_messages(db: Session, snapshot_id: uuid.UUID) -> list[PackMessage]:
    return list(
        db.scalars(
            select(PackMessage)
            .where(PackMessage.snapshot_id == snapshot_id, PackMessage.deleted_at.is_(None))
            .order_by(PackMessage.created_at)
        )
    )


def _attached_blocks(db: Session, snapshot_id: uuid.UUID, refs: list[uuid.UUID]) -> list[PackBlock]:
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


def _pack_blocks(db: Session, snapshot_id: uuid.UUID) -> list[PackBlock]:
    return list(
        db.scalars(
            select(PackBlock)
            .join(PackSection, PackBlock.section_id == PackSection.id)
            .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
            .where(
                PackBlock.deleted_at.is_(None),
                KnowledgePack.snapshot_id == snapshot_id,
                KnowledgePack.deleted_at.is_(None),
            )
            .options(joinedload(PackBlock.section))
            .order_by(PackSection.position, PackBlock.position)
        )
    )


def _pack_context(blocks: list[PackBlock]) -> str:
    """Render the authored pack in reading order within a predictable prompt budget.

    The previous chat prompt exposed only the first 80 characters of each block,
    which made questions about later details impossible even though the answer
    could cite those blocks. The pack is already the article's compact reading
    representation, so it is the best primary context for deep follow-ups.
    """

    parts: list[str] = []
    used = 0
    for block in blocks:
        text = _block_text(block).strip()
        if not text:
            continue
        heading = block.section.heading or "Untitled section"
        entry = f"[block id={block.id}; section={heading}; type={block.block_type.value}]\n{text}"
        remaining = _MAX_PACK_CONTEXT_CHARS - used
        if remaining <= 0:
            break
        if len(entry) > remaining:
            entry = entry[:remaining]
        parts.append(entry)
        used += len(entry) + 2
    return "\n\n".join(parts)


_MARKER_RE = re.compile(r"\[\[block:([0-9a-fA-F-]{36})\]\]")
_MAX_HOLDBACK = 48  # longest possible partial marker


class MarkerFilter:
    """Incrementally strip [[block:<uuid>]] citation markers from a token
    stream, collecting the cited ids. Text that merely looks like the start of
    a marker is held back until it resolves."""

    def __init__(self) -> None:
        self.refs: list[uuid.UUID] = []
        self.text = ""
        self._buf = ""

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            m = _MARKER_RE.search(self._buf)
            if m:
                out.append(self._buf[: m.start()])
                ref = uuid.UUID(m.group(1))
                if ref not in self.refs:
                    self.refs.append(ref)
                self._buf = self._buf[m.end() :]
                continue
            idx = self._buf.rfind("[[")
            if idx != -1 and len(self._buf) - idx < _MAX_HOLDBACK:
                out.append(self._buf[:idx])
                self._buf = self._buf[idx:]
            else:
                out.append(self._buf)
                self._buf = ""
            break
        clean = "".join(out)
        self.text += clean
        return clean

    def flush(self) -> str:
        tail, self._buf = self._buf, ""
        self.text += tail
        return tail


def _grounding_system(db: Session, snapshot_id: uuid.UUID, attached: list[PackBlock]) -> str:
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
        blocks_txt = "\n".join(
            f"- [block id={b.id}; type={b.block_type.value}] {_block_text(b)}" for b in attached
        )
        parts.append("The reader is asking specifically about these blocks:\n" + blocks_txt)
    citable = _pack_blocks(db, snapshot_id)
    if citable:
        parts.append("Knowledge pack content:\n" + _pack_context(citable))
        parts.append(
            "When a sentence draws on a specific block, cite it inline as "
            "[[block:<id>]] immediately after that sentence, using only ids "
            "from the knowledge pack content above."
        )
    parts.append(f"Source excerpt:\n{body[:_MAX_SOURCE_CHARS]}")
    return "\n".join(parts)


async def answer_stream(
    db: Session,
    snapshot_id: uuid.UUID,
    question: str,
    block_refs: list[uuid.UUID] | None = None,
    *,
    provider: LLMProvider | None = None,
) -> AsyncIterator[dict[str, Any]]:
    refs = [uuid.UUID(str(r)) for r in (block_refs or [])]
    attached = _attached_blocks(db, snapshot_id, refs)
    attached_ids = [b.id for b in attached]
    source = db.get(Source, snapshot_id)

    user_msg = PackMessage(
        snapshot_id=snapshot_id,
        role=ChatRole.user,
        content=question,
        block_refs=[str(r) for r in attached_ids],
    )
    db.add(user_msg)
    db.flush()

    history = list_messages(db, snapshot_id)
    messages = [
        ChatMessage(role="user" if m.role is ChatRole.user else "assistant", content=m.content)
        for m in history[-_MAX_HISTORY_MESSAGES:]
    ]
    system = _grounding_system(db, snapshot_id, attached)
    mf = MarkerFilter()
    try:
        if provider is not None:
            cfg = ModelConfig()  # injected fakes ignore the config
            prov = provider
        elif source is None:
            raise LookupError("snapshot not found")  # routes 404 before this
        else:
            cfg = resolve_model_config(db, source.owner_id)
            prov = get_spec(cfg.provider).adapter
        async for ev in prov.stream_chat(system=system, messages=messages, tools=None, config=cfg):
            if isinstance(ev, TextDelta):
                clean = mf.feed(ev.text)
                if clean:
                    yield {"type": "delta", "text": clean}
        tail = mf.flush()
        if tail:
            yield {"type": "delta", "text": tail}
    except LLMNotConfiguredError:
        db.rollback()
        yield {"type": "error", "code": "llm_not_configured"}
        return
    except LLMAuthError:
        db.rollback()
        yield {"type": "error", "code": "llm_key_invalid"}
        return
    except LLMRateLimitError:
        db.rollback()
        yield {"type": "error", "code": "llm_rate_limited"}
        return
    except LLMError:
        db.rollback()
        yield {"type": "error", "code": "llm_error"}
        return

    valid = {b.id for b in _pack_blocks(db, snapshot_id)}
    assistant_msg = PackMessage(
        snapshot_id=snapshot_id,
        role=ChatRole.assistant,
        content=mf.text,
        block_refs=[str(r) for r in mf.refs if r in valid],
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    yield {
        "type": "done",
        "message": {
            "id": str(assistant_msg.id),
            "role": "assistant",
            "content": assistant_msg.content,
            "block_refs": assistant_msg.block_refs,
            "created_at": assistant_msg.created_at.isoformat(),
        },
    }
