# Immersive reader redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the snapshot reader into an adaptive three-zone surface (collapsible nav + chat, fluid centered reading column), replace the dead "Original" tab with an origin-link icon, and replace per-block chat with one article-scoped conversation that accepts block attachments.

**Architecture:** Backend: a new snapshot-scoped `PackMessage` (with `block_refs`) replaces block-scoped `PackBlockMessage`; `chat.py` grounds on the whole pack + attached blocks. Frontend: `/snapshots` becomes full-bleed and is wrapped by a new client `ReaderLayout` that reuses the existing `<Sidebar/>`, owns nav/chat collapse state, and exposes an `addToChat` context; blocks call it instead of opening a per-block panel.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic, Pydantic → OpenAPI → `@gulp/api-client`, Next.js App Router + CSS Modules, pytest + vitest/RTL.

## Global Constraints

- **Web-first only** — no `apps/mobile`.
- **Backend through `@gulp/api-client`** in web; **contract is the source of truth** — run `just gen-client` after schema changes.
- **API routers thin** — logic in `app/services`.
- **vitest = classic JSX transform** — JSX files (components AND tests) `import React`; JSX-free `.ts` files must not.
- **Tests per-package** — `cd services/api && uv run pytest ...`; web via `pnpm --filter @gulp/web test`.
- **Chat stays synchronous** (no streaming); **no document-outline/TOC** this spec.
- **`just lint` green** before the final commit; `just migrate-up` needs local infra (`just up`); ignore the 2 pre-existing `schema.gen.ts` dup `tsc` warnings.
- Reuse tokens: `--measure` (720), `--sidebar-w` (240), `--border`, `--surface`, `--text-muted`, `--blue-50/700`.

---

## File Structure

**Backend**
- Create: `services/shared/gulp_shared/models/pack_message.py` (`PackMessage` + `ChatRole`).
- Delete: `services/shared/gulp_shared/models/pack_block_message.py`.
- Modify: `services/shared/gulp_shared/models/__init__.py` (swap export), `services/api/app/services/chat.py` (snapshot-scoped + attachments), `services/api/app/services/snapshots.py` (delete cascade), `services/api/app/schemas/chat.py` (`block_refs`), `services/api/app/routers/pack.py` (message endpoints).
- Migration: one Alembic revision (drop `pack_block_messages`, create `pack_messages`).
- Test: `services/api/tests/test_pack_chat.py` (replaces `test_block_chat.py`).

**Contract**
- Modify: `packages/api-client/src/index.ts` — `getPackMessages`/`postPackMessage` replace `getBlockMessages`/`postBlockMessage`.

**Web**
- Create: `apps/web/components/snapshot/ReaderChatContext.tsx`, `ReaderLayout.tsx` (+ `.module.css`), `ReaderTopBar.tsx` (+ `.module.css`).
- Modify: `apps/web/components/shell/FullBleedGate.tsx` (full-bleed `/snapshots`), `apps/web/app/snapshots/[id]/page.tsx` (wrap in `ReaderLayout`), `components/snapshot/ReaderToggle.tsx` (Pack/Cards), `ChatPanel.tsx` (+ `.module.css`) (snapshot-scoped + attachments), `PackReport.tsx` (context add-to-chat), `BlockCell.tsx` + `BlockToolbar.tsx` (`onAddToChat`).
- Test: `ChatPanel.test.tsx`, `ReaderLayout.test.tsx`, `ReaderToggle.test.tsx` (new/updated).

**Docs:** `docs/01`, `docs/02`, `docs/03`.

---

## Task 1: Backend — `PackMessage` model replaces `PackBlockMessage`

**Files:**
- Create: `services/shared/gulp_shared/models/pack_message.py`
- Delete: `services/shared/gulp_shared/models/pack_block_message.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`

**Interfaces:**
- Produces: `PackMessage(snapshot_id: uuid, role: ChatRole, content: str, block_refs: list)`; `ChatRole` (user/assistant) now lives in `pack_message`.

- [ ] **Step 1: Create the model** — `services/shared/gulp_shared/models/pack_message.py`:

```python
"""PackMessage — one turn of a snapshot-scoped (article) chat thread; a user
turn may attach block ids in `block_refs` (spec 2026-07-10 reader redesign)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ChatRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class PackMessage(TimestampedBase, Base):
    __tablename__ = "pack_messages"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"))
    content: Mapped[str] = mapped_column(Text)
    # block ids (as strings) the user attached to this turn; empty otherwise.
    block_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)
```

- [ ] **Step 2: Delete the old model**

Run: `rm services/shared/gulp_shared/models/pack_block_message.py`

- [ ] **Step 3: Swap the export** — open `services/shared/gulp_shared/models/__init__.py`; replace the `pack_block_message` import (`PackBlockMessage`, and `ChatRole` if re-exported there) with the `pack_message` equivalents (`from .pack_message import ChatRole, PackMessage`), and update `__all__` similarly. Keep every other export unchanged.

- [ ] **Step 4: Verify models import cleanly**

Run: `cd services/api && uv run python -c "from gulp_shared.models import PackMessage, ChatRole; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add services/shared/gulp_shared/models/
git commit -m "feat(shared): PackMessage (snapshot-scoped chat) replaces PackBlockMessage"
```

---

## Task 2: Backend — snapshot-scoped chat service + delete cascade

**Files:**
- Modify: `services/api/app/services/chat.py`
- Modify: `services/api/app/services/snapshots.py`
- Test: `services/api/tests/test_pack_chat.py` (create), remove `test_block_chat.py`

**Interfaces:**
- Consumes: `PackMessage`, `ChatRole` (Task 1).
- Produces: `list_messages(db, snapshot_id) -> list[PackMessage]`; `answer_question(db, snapshot_id, question, block_refs=None, *, provider=None) -> PackMessage`.

- [ ] **Step 1: Write the failing test** — create `services/api/tests/test_pack_chat.py`:

```python
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
    KnowledgePack, PackBlock, PackBlockType, PackSection, PackStatus, PackType,
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
```

Then remove the obsolete file: `rm services/api/tests/test_block_chat.py`

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_pack_chat.py -q`
Expected: FAIL — `answer_question` still has the old block-scoped signature / endpoints don't exist.

- [ ] **Step 3: Rewrite the chat service** — replace `services/api/app/services/chat.py` entirely:

```python
"""Snapshot-scoped article chat: assemble context (+ attached blocks), call the
LLM, persist the thread (spec 2026-07-10 reader redesign)."""

import uuid

from gulp_shared.llm import LLMProvider, ModelConfig, complete_structured
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
    messages = [{"role": m.role.value, "content": m.content} for m in history]
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
```

- [ ] **Step 4: Update the delete cascade** — in `services/api/app/services/snapshots.py`: change the import `from gulp_shared.models.pack_block_message import PackBlockMessage` → `from gulp_shared.models.pack_message import PackMessage`, and replace the block-message stamp. The block-ids branch becomes:

```python
    if block_ids:
        _stamp(PackBlock, PackBlock.id.in_(block_ids))
```

and add, alongside the other `_stamp(...)` calls (e.g. next to `_stamp(SourceTag, ...)`):

```python
    _stamp(PackMessage, PackMessage.snapshot_id == source.id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_pack_chat.py -q`
Expected: FAIL still at the endpoint tests (routes not added yet) but the two service-level tests PASS. If the endpoint tests are the only failures, proceed to Task 3.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/services/chat.py services/api/app/services/snapshots.py services/api/tests/test_pack_chat.py
git rm services/api/tests/test_block_chat.py
git commit -m "feat(api): snapshot-scoped chat service with block attachments"
```

---

## Task 3: Backend — chat schema + message endpoints

**Files:**
- Modify: `services/api/app/schemas/chat.py`
- Modify: `services/api/app/routers/pack.py`

**Interfaces:**
- Consumes: `answer_question`/`list_messages` (Task 2).
- Produces: `GET /snapshots/{id}/messages` → `list[MessageOut]`; `POST /snapshots/{id}/messages` `{content, block_refs?}` → `MessageOut` (with `block_refs: uuid[]`).

- [ ] **Step 1: Update the schema** — replace `services/api/app/schemas/chat.py`:

```python
"""Article-chat contract — becomes the OpenAPI types the web client reads."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    block_refs: list[uuid.UUID]
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    content: str
    block_refs: list[uuid.UUID] = []
```

- [ ] **Step 2: Replace the routes** — in `services/api/app/routers/pack.py`, remove `list_block_messages_route` and `post_block_message_route` (the two `.../blocks/{block_id}/messages` handlers) and add:

```python
@router.get("/snapshots/{snapshot_id}/messages", response_model=list[MessageOut])
def list_messages_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Any]:
    _owned_snapshot(db, snapshot_id, user)
    return list_messages(db, snapshot_id)


@router.post("/snapshots/{snapshot_id}/messages", response_model=MessageOut, status_code=201)
async def post_message_route(
    snapshot_id: uuid.UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    _owned_snapshot(db, snapshot_id, user)
    return await answer_question(db, snapshot_id, body.content, body.block_refs)
```

The imports (`MessageCreate, MessageOut`, `answer_question, list_messages`) are already present from the block version — keep them.

- [ ] **Step 3: Run test to verify it passes**

Run: `cd services/api && uv run pytest tests/test_pack_chat.py -q`
Expected: PASS (all 4).

- [ ] **Step 4: Full API suite (catch anything referencing the old model/routes)**

Run: `cd services/api && uv run pytest -q`
Expected: PASS. (If a test still imports `pack_block_message` or the old routes, update it to the `pack_message` / `/messages` equivalents.)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/schemas/chat.py services/api/app/routers/pack.py
git commit -m "feat(api): article message endpoints (/snapshots/{id}/messages) with block_refs"
```

---

## Task 4: Alembic migration + regenerate client + TS helpers

**Files:**
- Create: one migration under `services/api/alembic/versions/`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Produces: `Snapshot`-independent `MessageOut` on the new path; `getPackMessages(id)`, `postPackMessage(id, {content, block_refs})`.

- [ ] **Step 1: Autogenerate the migration** (needs local infra — `just up` first if not running)

Run: `just migrate "reader chat: pack_messages replaces pack_block_messages"`
Then open the generated file in `services/api/alembic/versions/`.

- [ ] **Step 2: Verify/fix the migration body.** It must: `op.drop_table("pack_block_messages")`; `op.create_table("pack_messages", ...)` with `id/created_at/updated_at/deleted_at` (TimestampedBase columns, like the other tables' migrations), `snapshot_id` FK → `sources.id` (`ondelete="CASCADE"`, indexed), `role` as `sa.Enum(..., name="chat_role", create_type=False)` (the enum type already exists — do NOT recreate or drop it), `content` Text, `block_refs` `sa.JSON()`. Ensure `downgrade` reverses (drop `pack_messages`, recreate `pack_block_messages`). Remove any autogen line that drops/creates the `chat_role` enum type.

- [ ] **Step 3: Apply and sanity-check**

Run: `just migrate-up`
Expected: applies cleanly. Then: `cd services/api && uv run pytest -q` → still green.

- [ ] **Step 4: Regenerate the client**

Run: `just gen-client`
Then: `grep -n "snapshot_id}/messages\|block_refs" packages/api-client/src/schema.gen.ts | head`
Expected: the `/snapshots/{snapshot_id}/messages` path and `block_refs` appear; the old `/blocks/{block_id}/messages` path is gone.

- [ ] **Step 5: Replace the client helpers** — in `packages/api-client/src/index.ts`, replace the `MessageOut`/`MessageCreateBody` type aliases and the `getBlockMessages`/`postBlockMessage` functions (the block-messages block near the bottom) with:

```typescript
export type MessageOut =
  paths["/snapshots/{snapshot_id}/messages"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MessageCreateBody =
  paths["/snapshots/{snapshot_id}/messages"]["post"]["requestBody"]["content"]["application/json"];

export async function getPackMessages(snapshotId: string): Promise<MessageOut[]> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/messages", {
    params: { path: { snapshot_id: snapshotId } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("fetch messages failed");
  return data;
}

export async function postPackMessage(
  snapshotId: string,
  body: MessageCreateBody,
): Promise<MessageOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/messages", {
    params: { path: { snapshot_id: snapshotId } },
    body,
  });
  if (error || !data) throw new Error("post message failed");
  return data;
}
```

- [ ] **Step 6: Typecheck the client**

Run: `pnpm --filter @gulp/api-client exec tsc --noEmit 2>&1 | grep -v "schema.gen.ts" | grep "error TS"` → expect no output.

- [ ] **Step 7: Commit**

```bash
git add services/api/alembic packages/api-client
git commit -m "feat(api-client): pack message endpoints migration + getPackMessages/postPackMessage"
```

---

## Task 5: Web — trim ReaderToggle to Pack/Cards

**Files:**
- Modify: `apps/web/components/snapshot/ReaderToggle.tsx`
- Test: `apps/web/components/snapshot/ReaderToggle.test.tsx` (create)

**Interfaces:**
- Produces: `<ReaderToggle pack snapshotId cardsStatus />` (no `original`).

- [ ] **Step 1: Write the failing test** — create `apps/web/components/snapshot/ReaderToggle.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { PackOut } from "@gulp/api-client";
import { ReaderToggle } from "./ReaderToggle";

vi.mock("@gulp/api-client", () => ({ getFigures: vi.fn().mockResolvedValue([]) }));
vi.mock("@/components/cards/CardsView", () => ({ CardsView: () => <div>cards</div> }));

afterEach(cleanup);

const pack = {
  snapshot_id: "00000000-0000-0000-0000-000000000000",
  status: "ready", pack_type: "article", title: "T", summary: null,
  core_contributions: [], key_insight: null, sections: [], references: [],
} as unknown as PackOut;

describe("ReaderToggle", () => {
  it("shows Pack and Cards tabs but not Original", () => {
    render(<ReaderToggle pack={pack} snapshotId="s1" cardsStatus={null} />);
    expect(screen.getByRole("button", { name: "Pack" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cards" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Original" })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- ReaderToggle`
Expected: FAIL — "Original" button still present / `original` prop required.

- [ ] **Step 3: Rewrite** — replace `apps/web/components/snapshot/ReaderToggle.tsx`:

```tsx
"use client";

import React, { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { CardsView } from "@/components/cards/CardsView";
import { PackReport } from "./PackReport";
import styles from "./ReaderToggle.module.css";

type CardsStatus = "generating" | "ready" | "failed" | null;

export function ReaderToggle({
  pack,
  snapshotId,
  cardsStatus,
}: {
  pack: PackOut;
  snapshotId: string;
  cardsStatus: CardsStatus;
}) {
  const [view, setView] = useState<"pack" | "cards">("pack");
  return (
    <div>
      <div className={styles.bar}>
        <button
          className={`${styles.tab} ${view === "pack" ? styles.active : ""}`}
          onClick={() => setView("pack")}
        >
          Pack
        </button>
        <button
          className={`${styles.tab} ${view === "cards" ? styles.active : ""}`}
          onClick={() => setView("cards")}
        >
          Cards
        </button>
      </div>
      {view === "pack" && (
        <div className={styles.main}>
          <PackReport pack={pack} />
        </div>
      )}
      {view === "cards" && (
        <div className={styles.main}>
          <CardsView snapshotId={snapshotId} initialCardsStatus={cardsStatus} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test -- ReaderToggle`
Expected: PASS. (Don't commit yet — `page.tsx` still passes `original`; fixed in Task 8. Commit at the end of Task 8, or make this compile-clean by updating the `renderPack` call now.)

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/ReaderToggle.tsx apps/web/components/snapshot/ReaderToggle.test.tsx
git commit -m "feat(web): ReaderToggle drops the Original tab (Pack/Cards only)"
```

---

## Task 6: Web — reader chat context + reworked ChatPanel

**Files:**
- Create: `apps/web/components/snapshot/ReaderChatContext.tsx`
- Modify: `apps/web/components/snapshot/ChatPanel.tsx`, `apps/web/components/snapshot/ChatPanel.module.css`
- Test: `apps/web/components/snapshot/ChatPanel.test.tsx` (create)

**Interfaces:**
- Produces: `type ChatAttachment = { id: string; label: string }`; `ReaderChatCtx`, `useReaderChat()`; `<ChatPanel snapshotId attachments onRemoveAttachment onClose />`.

- [ ] **Step 1: Create the context** — `apps/web/components/snapshot/ReaderChatContext.tsx`:

```tsx
"use client";

import { createContext, useContext } from "react";

export type ChatAttachment = { id: string; label: string };

type ReaderChat = { addToChat: (a: ChatAttachment) => void };

export const ReaderChatCtx = createContext<ReaderChat | null>(null);

export function useReaderChat(): ReaderChat | null {
  return useContext(ReaderChatCtx);
}
```

- [ ] **Step 2: Write the failing ChatPanel test** — `apps/web/components/snapshot/ChatPanel.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "./ChatPanel";

const getPackMessages = vi.fn().mockResolvedValue([]);
const postPackMessage = vi.fn().mockResolvedValue({
  id: "a1", role: "assistant", content: "Answer.", block_refs: [], created_at: "",
});
vi.mock("@gulp/api-client", () => ({
  getPackMessages: (...a: unknown[]) => getPackMessages(...a),
  postPackMessage: (...a: unknown[]) => postPackMessage(...a),
}));

afterEach(() => { cleanup(); getPackMessages.mockClear(); postPackMessage.mockClear(); });

describe("ChatPanel", () => {
  it("renders attachment chips and removes them", async () => {
    const onRemove = vi.fn();
    render(
      <ChatPanel snapshotId="s1" attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={onRemove} onClose={() => {}} />,
    );
    expect(screen.getByText("para")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Remove para" }));
    expect(onRemove).toHaveBeenCalledWith("b1");
  });

  it("sends with the attached block_refs", async () => {
    render(
      <ChatPanel snapshotId="s1" attachments={[{ id: "b1", label: "para" }]}
        onRemoveAttachment={() => {}} onClose={() => {}} />,
    );
    await userEvent.type(screen.getByRole("textbox"), "hello");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(postPackMessage).toHaveBeenCalledWith("s1", { content: "hello", block_refs: ["b1"] }),
    );
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- ChatPanel`
Expected: FAIL — `ChatPanel` still block-scoped (`blockId` prop, `postBlockMessage`).

- [ ] **Step 4: Rewrite ChatPanel** — replace `apps/web/components/snapshot/ChatPanel.tsx`:

```tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
import { getPackMessages, postPackMessage, type MessageOut } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import type { ChatAttachment } from "./ReaderChatContext";
import styles from "./ChatPanel.module.css";

export function ChatPanel({
  snapshotId,
  attachments,
  onRemoveAttachment,
  onClose,
}: {
  snapshotId: string;
  attachments: ChatAttachment[];
  onRemoveAttachment: (id: string) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tmpIdRef = useRef(0);

  useEffect(() => {
    let active = true;
    setMessages([]);
    setError(null);
    getPackMessages(snapshotId)
      .then((m) => { if (active) setMessages(m); })
      .catch(() => { if (active) setError("Couldn't load the conversation."); });
    return () => { active = false; };
  }, [snapshotId]);

  async function send() {
    const q = draft.trim();
    if (!q || sending) return;
    const refs = attachments.map((a) => a.id);
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: MessageOut = {
      id: `tmp-${tmpIdRef.current++}`, role: "user", content: q, block_refs: refs, created_at: "",
    };
    setMessages((m) => [...m, optimistic]);
    try {
      const answer = await postPackMessage(snapshotId, { content: q, block_refs: refs });
      setMessages((m) => [...m, answer]);
    } catch {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(q);
      setError("Couldn't send — try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className={styles.panel} aria-label="Article chat">
      <div className={styles.header}>
        <span className="t-label">Chat</span>
        <button type="button" className={styles.close} aria-label="Close chat" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className={styles.messages}>
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? styles.user : styles.assistant}>
            {m.content}
          </div>
        ))}
        {sending && <div className={styles.thinking}>Thinking…</div>}
      </div>
      {error && (
        <div className={styles.err} role="alert">
          {error}
        </div>
      )}
      {attachments.length > 0 && (
        <div className={styles.attachments}>
          {attachments.map((a) => (
            <span key={a.id} className={styles.chip}>
              {a.label}
              <button type="button" aria-label={`Remove ${a.label}`} onClick={() => onRemoveAttachment(a.id)}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className={styles.composer}>
        <textarea
          aria-label="Ask about this article"
          className={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={sending}
        />
        <Button variant="primary" onClick={send} disabled={sending || !draft.trim()}>
          Send
        </Button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 5: Rework the panel CSS** — replace `apps/web/components/snapshot/ChatPanel.module.css` (it now fills a grid cell, not a fixed overlay):

```css
.panel {
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
  background: var(--surface, #fffdf6);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.close {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1rem;
  color: var(--text-muted, #777);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user,
.assistant {
  padding: 8px 12px;
  border-radius: 10px;
  max-width: 90%;
  white-space: pre-wrap;
  line-height: 1.45;
}

.user {
  align-self: flex-end;
  background: var(--blue-50, #fff4c2);
}

.assistant {
  align-self: flex-start;
  background: var(--fill, #f2ecd9);
}

.thinking {
  align-self: flex-start;
  color: var(--text-muted, #777);
  font-style: italic;
}

.err {
  padding: 8px 16px;
  color: #b00020;
}

.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 16px 0;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.78em;
  padding: 2px 4px 2px 8px;
  border: 1px solid var(--border-strong, #d8cca8);
  border-radius: 999px;
  background: var(--blue-50, #fff4c2);
}

.chip button {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-muted, #777);
}

.composer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.input {
  flex: 1;
  resize: none;
  min-height: 40px;
  font: inherit;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg, #fbf7ea);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test -- ChatPanel`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/snapshot/ReaderChatContext.tsx apps/web/components/snapshot/ChatPanel.tsx apps/web/components/snapshot/ChatPanel.module.css apps/web/components/snapshot/ChatPanel.test.tsx
git commit -m "feat(web): article-scoped ChatPanel with attachment chips"
```

---

## Task 7: Web — block "add to chat" wiring

**Files:**
- Modify: `apps/web/components/snapshot/BlockToolbar.tsx`, `BlockCell.tsx`, `PackReport.tsx`

**Interfaces:**
- Consumes: `useReaderChat()` (Task 6).
- Produces: block toolbar "add to chat" → `addToChat({ id, label })`.

- [ ] **Step 1: Rename the toolbar action** — in `apps/web/components/snapshot/BlockToolbar.tsx`, rename the `onDiscuss` prop to `onAddToChat` (in the type and destructure), and change the button's `aria-label="Discuss block"` `onClick={onDiscuss}` → `aria-label="Add to chat"` `onClick={onAddToChat}` (keep the 💬 glyph).

- [ ] **Step 2: Thread it through BlockCell** — in `apps/web/components/snapshot/BlockCell.tsx`, rename the `onDiscuss` prop to `onAddToChat` (type + destructure) and pass `onAddToChat={onAddToChat}` to `<BlockToolbar>`.

- [ ] **Step 3: Rewire PackReport to the context** — in `apps/web/components/snapshot/PackReport.tsx`:
  - Remove `import { ChatPanel } from "./ChatPanel";`, the `selectedBlockId` state, and the `{selectedBlockId && <ChatPanel .../>}` block at the end (and its wrapping fragment can stay).
  - Add `import { useReaderChat } from "./ReaderChatContext";` and, inside the component, `const chat = useReaderChat();`.
  - Add this helper above the component:

    ```tsx
    const preview = (s: string) => {
      const t = s.replace(/\s+/g, " ").trim();
      return t.length > 32 ? `${t.slice(0, 32)}…` : t || "Block";
    };

    function attachmentLabel(block: PackBlockOut): string {
      switch (block.type) {
        case "prose": return preview(block.content);
        case "formula": return preview(block.explanation || block.latex);
        case "list": return preview(block.items[0] ?? "List");
        case "figure": return block.label || "Figure";
        case "table": return block.caption || "Table";
        case "code": return "Code";
        default: return "Block";
      }
    }
    ```

  - Change the `BlockCell` prop `onDiscuss={() => setSelectedBlockId(block.id)}` → `onAddToChat={() => chat?.addToChat({ id: block.id, label: attachmentLabel(block) })}`.

- [ ] **Step 4: Typecheck (no test change — behavior verified via ReaderLayout in Task 8)**

Run: `pnpm --filter @gulp/web exec tsc --noEmit 2>&1 | grep -E "PackReport|BlockCell|BlockToolbar" | grep "error TS"` → expect no output.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/BlockToolbar.tsx apps/web/components/snapshot/BlockCell.tsx apps/web/components/snapshot/PackReport.tsx
git commit -m "feat(web): block toolbar 'add to chat' feeds the article thread"
```

---

## Task 8: Web — ReaderLayout, top bar, full-bleed reader

**Files:**
- Create: `apps/web/components/snapshot/ReaderLayout.tsx` (+ `.module.css`), `ReaderTopBar.tsx` (+ `.module.css`)
- Modify: `apps/web/components/shell/FullBleedGate.tsx`, `apps/web/app/snapshots/[id]/page.tsx`
- Test: `apps/web/components/snapshot/ReaderLayout.test.tsx` (create)

**Interfaces:**
- Consumes: `ReaderChatCtx` (Task 6), `ChatPanel` (Task 6), `ReaderToggle` (Task 5).
- Produces: `<ReaderLayout sidebar snapshotId title genre originUrl packReady>{center}</ReaderLayout>`.

- [ ] **Step 1: Write the failing test** — `apps/web/components/snapshot/ReaderLayout.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReaderLayout } from "./ReaderLayout";

vi.mock("@gulp/api-client", () => ({
  getPackMessages: vi.fn().mockResolvedValue([]),
  postPackMessage: vi.fn().mockResolvedValue({}),
}));
vi.mock("./GenreSelect", () => ({ GenreSelect: () => <div>genre</div> }));

afterEach(cleanup);

function renderReader(packReady = true, originUrl: string | null = "https://x.com/a") {
  return render(
    <ReaderLayout sidebar={<nav>SIDENAV</nav>} snapshotId="s1" title="My Article"
      genre={null} originUrl={originUrl} packReady={packReady}>
      <div>BODY</div>
    </ReaderLayout>,
  );
}

describe("ReaderLayout", () => {
  it("toggles the nav", async () => {
    renderReader();
    expect(screen.getByText("SIDENAV")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Hide sidebar/ }));
    expect(screen.queryByText("SIDENAV")).toBeNull();
  });

  it("toggles the chat panel when the pack is ready", async () => {
    renderReader(true);
    expect(screen.queryByRole("complementary", { name: "Article chat" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Toggle chat" }));
    expect(screen.getByRole("complementary", { name: "Article chat" })).toBeTruthy();
  });

  it("shows the origin link and hides the chat toggle when not ready", () => {
    renderReader(false);
    expect(screen.getByRole("link", { name: /Open original/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Toggle chat" })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test -- ReaderLayout`
Expected: FAIL — module not found.

- [ ] **Step 3: Create the top bar** — `apps/web/components/snapshot/ReaderTopBar.tsx`:

```tsx
"use client";

import React from "react";
import Link from "next/link";
import { GenreSelect } from "./GenreSelect";
import styles from "./ReaderTopBar.module.css";

export function ReaderTopBar({
  title,
  genre,
  snapshotId,
  originUrl,
  navOpen,
  onToggleNav,
  chatEnabled,
  chatOpen,
  onToggleChat,
}: {
  title: string;
  genre: React.ComponentProps<typeof GenreSelect>["genre"];
  snapshotId: string;
  originUrl: string | null;
  navOpen: boolean;
  onToggleNav: () => void;
  chatEnabled: boolean;
  chatOpen: boolean;
  onToggleChat: () => void;
}) {
  return (
    <header className={styles.bar}>
      <button
        type="button"
        className={styles.icon}
        aria-label={navOpen ? "Hide sidebar" : "Show sidebar"}
        aria-pressed={!navOpen}
        onClick={onToggleNav}
      >
        ⇤
      </button>
      <Link href="/inbox" className={styles.back}>
        ← Inbox
      </Link>
      <h1 className={`t-title-m ${styles.title}`}>{title}</h1>
      <GenreSelect snapshotId={snapshotId} genre={genre} />
      <span className={styles.spacer} />
      {originUrl && (
        <a
          className={styles.icon}
          href={originUrl}
          target="_blank"
          rel="noreferrer"
          aria-label="Open original"
          title="Open original"
        >
          ↗
        </a>
      )}
      {chatEnabled && (
        <button
          type="button"
          className={styles.icon}
          aria-label="Toggle chat"
          aria-pressed={chatOpen}
          onClick={onToggleChat}
        >
          💬
        </button>
      )}
    </header>
  );
}
```

- [ ] **Step 4: Top bar CSS** — `apps/web/components/snapshot/ReaderTopBar.module.css`:

```css
.bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg, #fbf7ea);
  z-index: 5;
}

.back {
  color: var(--text-muted, #777);
  text-decoration: none;
  white-space: nowrap;
}

.title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spacer {
  flex: 1;
}

.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  font-size: 1rem;
}

.icon:hover {
  background: var(--surface, #fffdf6);
  border-color: var(--border);
}

.icon[aria-pressed="true"] {
  background: var(--blue-50, #fff4c2);
  border-color: var(--border-strong, #d8cca8);
}
```

- [ ] **Step 5: Create ReaderLayout** — `apps/web/components/snapshot/ReaderLayout.tsx`:

```tsx
"use client";

import React, { useEffect, useState, type ReactNode } from "react";
import { ReaderChatCtx, type ChatAttachment } from "./ReaderChatContext";
import { ReaderTopBar } from "./ReaderTopBar";
import { ChatPanel } from "./ChatPanel";
import type { GenreSelect } from "./GenreSelect";
import styles from "./ReaderLayout.module.css";

export function ReaderLayout({
  sidebar,
  snapshotId,
  title,
  genre,
  originUrl,
  packReady,
  children,
}: {
  sidebar: ReactNode;
  snapshotId: string;
  title: string;
  genre: React.ComponentProps<typeof GenreSelect>["genre"];
  originUrl: string | null;
  packReady: boolean;
  children: ReactNode;
}) {
  const [navOpen, setNavOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);

  useEffect(() => {
    setNavOpen(localStorage.getItem("reader:navOpen") !== "false");
  }, []);
  useEffect(() => {
    localStorage.setItem("reader:navOpen", String(navOpen));
  }, [navOpen]);

  function addToChat(a: ChatAttachment) {
    setAttachments((xs) => (xs.some((x) => x.id === a.id) ? xs : [...xs, a]));
    setChatOpen(true);
  }
  function removeAttachment(id: string) {
    setAttachments((xs) => xs.filter((x) => x.id !== id));
  }

  const chatShown = packReady && chatOpen;

  return (
    <ReaderChatCtx.Provider value={{ addToChat }}>
      <div
        className={styles.layout}
        data-nav={navOpen ? "open" : "closed"}
        data-chat={chatShown ? "open" : "closed"}
      >
        {navOpen && <div className={styles.nav}>{sidebar}</div>}
        <div className={styles.center}>
          <ReaderTopBar
            title={title}
            genre={genre}
            snapshotId={snapshotId}
            originUrl={originUrl}
            navOpen={navOpen}
            onToggleNav={() => setNavOpen((v) => !v)}
            chatEnabled={packReady}
            chatOpen={chatOpen}
            onToggleChat={() => setChatOpen((v) => !v)}
          />
          <div className={styles.reading}>{children}</div>
        </div>
        {chatShown && (
          <div className={styles.chat}>
            <ChatPanel
              snapshotId={snapshotId}
              attachments={attachments}
              onRemoveAttachment={removeAttachment}
              onClose={() => setChatOpen(false)}
            />
          </div>
        )}
      </div>
    </ReaderChatCtx.Provider>
  );
}
```

- [ ] **Step 6: ReaderLayout CSS** — `apps/web/components/snapshot/ReaderLayout.module.css`:

```css
.layout {
  display: grid;
  grid-template-columns: 1fr;
  min-height: 100vh;
}

.layout[data-nav="open"] {
  grid-template-columns: var(--sidebar-w, 240px) 1fr;
}

.layout[data-nav="open"][data-chat="open"] {
  grid-template-columns: var(--sidebar-w, 240px) 1fr 380px;
}

.layout[data-nav="closed"][data-chat="open"] {
  grid-template-columns: 1fr 380px;
}

.nav {
  border-right: 1px solid var(--border);
  min-width: 0;
}

.center {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.reading {
  flex: 1;
  width: 100%;
  max-width: var(--measure, 720px);
  margin: 0 auto;
  padding: 24px;
}

.chat {
  min-width: 0;
  border-left: 1px solid var(--border);
}

@media (max-width: 900px) {
  .layout[data-nav="open"][data-chat="open"] {
    grid-template-columns: 1fr 320px;
  }
  .layout[data-nav="open"][data-chat="open"] .nav {
    display: none;
  }
}
```

- [ ] **Step 7: Make `/snapshots` full-bleed** — in `apps/web/components/shell/FullBleedGate.tsx`, change the constant to:

```tsx
const FULL_BLEED_PREFIXES = ["/gulp", "/snapshots"];
```

- [ ] **Step 8: Wrap the page** — replace `apps/web/app/snapshots/[id]/page.tsx`:

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPack, getSnapshot } from "@gulp/api-client";
import { Sidebar } from "@/components/shell/Sidebar";
import { ReaderLayout } from "@/components/snapshot/ReaderLayout";
import { ReaderToggle } from "@/components/snapshot/ReaderToggle";
import { StartButton } from "@/components/snapshot/StartButton";
import { ExportActions } from "@/components/snapshot/ExportActions";
import { ProcessingPoller } from "@/components/snapshot/ProcessingPoller";
import styles from "@/components/snapshot/SnapshotStatusView.module.css";

export const dynamic = "force-dynamic";

export default async function SnapshotPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let snap;
  try {
    snap = await getSnapshot(id);
  } catch {
    notFound();
  }

  const body = (
    <>
      {snap.status === "unprocessed" && (
        <div className={styles.actions}>
          <StartButton id={id} />
          <ExportActions id={id} status={snap.status} />
        </div>
      )}

      {(snap.status === "processing" || snap.status === "queued") && (
        <>
          <ProcessingPoller id={id} />
          <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Reading it for you…</p>
          <div className={styles.skeleton} />
          <div className={styles.skeleton} />
          <div className={`${styles.skeleton} ${styles.short}`} />
        </>
      )}

      {snap.status === "needs_attention" && (
        <>
          <div className={styles.banner}>Couldn&apos;t fully read this.</div>
          <div className={styles.actions}>
            <StartButton id={id} label="Retry" />
            <ExportActions id={id} status={snap.status} />
          </div>
        </>
      )}

      {snap.status === "exported" && (
        <div className={styles.actions}>
          <ExportActions id={id} status={snap.status} />
          <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>
            Exported — run it in Claude Code, then upload the result zip.
          </p>
        </div>
      )}

      {snap.status === "ready" && (await renderPack(id, snap.cards_status ?? null))}
    </>
  );

  return (
    <ReaderLayout
      sidebar={<Sidebar />}
      snapshotId={id}
      title={snap.title}
      genre={snap.genre ?? null}
      originUrl={snap.origin_url}
      packReady={snap.status === "ready"}
    >
      {body}
    </ReaderLayout>
  );
}

async function renderPack(
  id: string,
  cardsStatus: "generating" | "ready" | "failed" | null,
) {
  const pack = await getPack(id);
  if (!pack) {
    return <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Pack not available.</p>;
  }
  return <ReaderToggle pack={pack} snapshotId={id} cardsStatus={cardsStatus} />;
}
```

Note: the origin link + title/genre moved into `ReaderTopBar`; the `Link` import stays only if still used — if `tsc`/eslint flags `Link` as unused, remove it. (The status bodies no longer render "Open original" — that lives in the top bar now.)

- [ ] **Step 9: Run the test to verify it passes**

Run: `pnpm --filter @gulp/web test -- ReaderLayout`
Expected: PASS (3 cases).

- [ ] **Step 10: Commit**

```bash
git add apps/web/components/snapshot/ReaderLayout.tsx apps/web/components/snapshot/ReaderLayout.module.css apps/web/components/snapshot/ReaderTopBar.tsx apps/web/components/snapshot/ReaderTopBar.module.css apps/web/components/shell/FullBleedGate.tsx apps/web/app/snapshots/[id]/page.tsx apps/web/components/snapshot/ReaderLayout.test.tsx
git commit -m "feat(web): full-bleed adaptive reader (collapsible nav + chat, origin icon)"
```

---

## Task 9: Docs — amend the specs

**Files:** `docs/01-interaction-spec.md`, `docs/02-data-model.md`, `docs/03-ui-system.md`

- [ ] **Step 1: `docs/02-data-model.md`** — where `PackBlockMessage` is described, replace with `PackMessage`: snapshot-scoped (`snapshot_id → Source`), `role`, `content`, `block_refs` (attached block ids); note the per-block chat was superseded 2026-07-10 and the table renamed via migration.

- [ ] **Step 2: `docs/03-ui-system.md`** — in the reader section, document the adaptive three-zone layout (collapsible nav + chat, fluid centered reading column at `--measure`), the `↗` origin icon replacing the Original tab, and the chat attachment chips.

- [ ] **Step 3: `docs/01-interaction-spec.md`** — in the reader/curation flow, note immersive collapse of nav + chat, and article-scoped chat with block "add to chat" (supersedes per-block threads).

- [ ] **Step 4: Commit**

```bash
git add docs/01-interaction-spec.md docs/02-data-model.md docs/03-ui-system.md
git commit -m "docs: immersive reader — adaptive layout, article chat, PackMessage"
```

---

## Task 10: Full-stack verification gate

- [ ] **Step 1: Client regen is a no-op**

Run: `just gen-client && git checkout -- packages/api-client 2>/dev/null; git status --porcelain packages/api-client`
(The `checkout` discards the known non-deterministic `schema.gen.ts` cards_job flip-flop; the meaningful diff was committed in Task 4.) Expect: clean.

- [ ] **Step 2: API suite**

Run: `cd services/api && uv run pytest -q`
Expected: PASS.

- [ ] **Step 3: Web suite** — also confirm no test still imports the removed `getBlockMessages`/`postBlockMessage` or per-block `ChatPanel` props.

Run: `pnpm --filter @gulp/web test`
Expected: PASS. (Fix any stragglers — e.g. an old per-block ChatPanel test — by deleting/retargeting.)

- [ ] **Step 4: Web typecheck (new code only)**

Run: `cd apps/web && pnpm exec tsc --noEmit 2>&1 | grep -v "schema.gen.ts" | grep -E "snapshot/(ReaderLayout|ReaderTopBar|ChatPanel|ReaderToggle|PackReport|BlockCell|BlockToolbar|ReaderChatContext)|app/snapshots" | grep "error TS"`
Expected: no output. (Pre-existing feeds `tsc` errors are unrelated — see `[[library-source-tags-shipped]]`.)

- [ ] **Step 5: Lint gate**

Run: `just lint`
Expected: green.

- [ ] **Step 6: Manual smoke** (needs `just up` + `just dev`)

- Open a `ready` snapshot. Confirm: three-zone layout; the `⇤` toggle hides/shows the left nav and the reading column re-centers; the `💬` toggle opens/closes the right chat; both closed = full-width immersive reading.
- Top bar shows `↗` (opens the source in a new tab); no "Original" tab remains (Pack / Cards only).
- Hover a block → "add to chat" (💬) adds a chip to the composer and opens chat; send a question → grounded answer; remove a chip with ×.
- Open a non-`ready` snapshot → nav + top bar present, no chat toggle.

- [ ] **Step 7: Final fixup commit (if needed)**

```bash
git add -A && git commit -m "chore: lint/test fixups for immersive reader"
```

---

## Self-Review

**Spec coverage:**
- Adaptive three-zone (collapsible nav + chat, fluid center) → Task 8 (`ReaderLayout` + CSS). ✓
- Origin `↗` replaces Original tab → Task 5 (trim) + Task 8 (top bar). ✓
- Unified article chat + block attachments, replaces per-block → Tasks 1–4 (model/service/schema/endpoints/migration/client) + 6 (panel) + 7 (add-to-chat). ✓
- Grounding with/without attachments → Task 2 tests. ✓
- Docs → Task 9. ✓
- Testing (pytest per-package; vitest classic-JSX) + gates → per-task tests + Task 10. ✓
- Out of scope (streaming, TOC, mobile) → absent. ✓

**Placeholder scan:** no TBD/TODO; code steps show full code; doc steps state the exact content. The `__init__.py` swap and migration-body verify are read-then-edit steps with explicit criteria (not code placeholders). ✓

**Type consistency:** `ChatRole`/`PackMessage`, `answer_question(db, snapshot_id, question, block_refs=None)`, `list_messages(db, snapshot_id)`, `MessageOut.block_refs`, `getPackMessages`/`postPackMessage`, `ChatAttachment{id,label}`, `ReaderChatCtx`/`useReaderChat`, `ReaderLayout`/`ReaderTopBar`/`ChatPanel` props — consistent across tasks. ✓
