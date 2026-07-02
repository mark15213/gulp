# Block-Editable Pack Reader — Phase 3a: Per-Block Chat Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add grounded, persisted per-block Q&A on the API side — a `PackBlockMessage` model, owner-scoped `GET/POST /snapshots/{sid}/blocks/{bid}/messages` endpoints that ground an LLM answer in the block + source, and the generated client helpers — by relocating the provider-agnostic LLM layer into `gulp_shared` so the API can call it synchronously.

**Architecture:** The worker's `app/llm/` package moves verbatim to `gulp_shared/llm/` (both API and worker then import it; the Anthropic provider already reads `gulp_shared.settings`). Chat reuses the existing structured path with a tiny `ChatAnswer{answer: str}` model — no new provider method. A `POST messages` route is `async`, persists the user turn, assembles grounding (block + section + pack title/key-insight + source excerpt, truncated), calls `complete_structured`, persists + returns the assistant turn. Ownership + pack-scoping mirror Phase 2a.

**Tech Stack:** FastAPI (async route) + Pydantic + SQLAlchemy (`services/api`, `services/shared`); Anthropic via the relocated provider-agnostic layer; Alembic; OpenAPI-generated `@gulp/api-client`; pytest.

## Global Constraints

- **Decision B1 (spec):** the LLM layer lives in `gulp_shared` and the API calls it **synchronously** (an `async` route awaiting `complete_structured`); chat is a "user is waiting" interaction, so `docs/CLAUDE.md` rule 4 (capture must not block on AI) does not apply.
- **The data model is the contract** (`docs/04 §2.5`): after changing `services/api/app/schemas`, run `just gen-client`.
- **API layering:** routers thin (authorize → call service → return); logic in `app/services`; persistence via `gulp_shared`. Services raise `LookupError` → router translates to 404.
- **Ownership + scoping:** every endpoint authorizes the snapshot owner via `_owned_snapshot` (404) AND scopes the block to that snapshot's pack via `load_block_scoped` (both already exist in `services/api/app/services/pack.py` from Phase 2a).
- **Grounding scope (spec Phase 3):** feed the block + its section heading + pack `title`/`key_insight` + the source's original text (`Source.content_body`), truncated to a token budget; instruct the model to answer from the source and say so when it doesn't cover the question. Persist history per block. NOT insert-as-block, NOT AI-rewrite. SSE streaming deferred (plain request/response v1).
- **No new runtime deps beyond `anthropic`** (moved into `gulp_shared`). English only.

**Environment (carry into every task):**
- API tests per-package: `cd services/api && uv run pytest tests/<f> -v`. Worker tests: `cd services/worker && uv run pytest -q`. (Repo-root pytest collides — see [[api-tests-per-package]].)
- Tests build the schema via `Base.metadata.create_all` (SQLite, `services/api/tests/conftest.py`), so a new model registered in `gulp_shared/models/__init__.py` is auto-created in tests — **no migration is needed for tests**; the migration is for real Postgres.
- **The working tree has PRE-EXISTING unrelated uncommitted changes** (services/shared, services/worker) AND an **untracked** migration `services/api/alembic/versions/c2d3e4f5a6b7_s2_pack_cascade_delete.py` (down_revision `a1b2c3d4e5f6`). Do NOT touch/commit any of it. Because that untracked file also chains off `a1b2c3d4e5f6`, running `alembic upgrade head` LOCALLY will report multiple heads — that is a pre-existing WIP artifact, NOT this branch's concern; do not "fix" it. Our new migration also chains off the committed head `a1b2c3d4e5f6`; on origin/main (no WIP file) it is a clean single head. Verify the migration by import + inspection, not `alembic upgrade`.
- Stage ONLY each task's exact files (`git add <paths>`; never `git add .`/`-A`).

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `services/shared/gulp_shared/llm/*` | provider-agnostic LLM layer | **moved** from `services/worker/app/llm/` |
| `services/shared/pyproject.toml` | shared deps | add `anthropic` |
| `services/worker/app/pipeline/digest.py` (+ worker tests) | LLM consumer | update import path |
| `services/shared/gulp_shared/models/pack_block_message.py` | chat message row | create |
| `services/shared/gulp_shared/models/__init__.py` | model registry | register `PackBlockMessage`/`ChatRole` |
| `services/api/alembic/versions/d3e4f5a6b7c8_s2_pack_block_messages.py` | migration | create (hand-written) |
| `services/api/app/schemas/chat.py` | message DTOs | create |
| `services/api/app/services/chat.py` | grounding + LLM call + persistence | create |
| `services/api/app/routers/pack.py` | messages routes | add GET/POST (async POST) |
| `services/api/tests/test_block_chat.py` | endpoint + service tests | create |
| `packages/api-client/*` | client + helpers | regenerate + `getBlockMessages`/`postBlockMessage` |

---

### Task 1: Relocate the LLM layer to `gulp_shared`

**Files:**
- Move: `services/worker/app/llm/{__init__,base,service,anthropic_provider}.py` → `services/shared/gulp_shared/llm/`
- Modify: `services/shared/pyproject.toml` (add `anthropic`)
- Modify: `services/worker/app/pipeline/digest.py` + any `app.llm` importer under `services/worker`
- Verify: worker + api suites stay green

**Interfaces:**
- Produces: `gulp_shared.llm` exports `complete_structured`, `register_provider`, `get_provider`, `AnthropicProvider`, `LLMError`, `LLMProvider`, `Message`, `ModelConfig` — same names as before, new import root `gulp_shared.llm`.

- [ ] **Step 1: Move the package (preserve history)**

Run:
```bash
cd /Users/shuaiwang/Documents/projects/gulp
git mv services/worker/app/llm services/shared/gulp_shared/llm
```

- [ ] **Step 2: Rewrite the package's internal imports**

In the moved files, replace `app.llm` → `gulp_shared.llm`:
- `services/shared/gulp_shared/llm/service.py`: `from app.llm.base import ...` → `from gulp_shared.llm.base import ...`
- `services/shared/gulp_shared/llm/anthropic_provider.py`: `from app.llm.base import ...` → `from gulp_shared.llm.base import ...` (the `from gulp_shared.settings import settings` line stays)
- `services/shared/gulp_shared/llm/__init__.py`: `from app.llm.X import ...` (three lines) → `from gulp_shared.llm.X import ...`
- `base.py` has no `app.llm` import — leave it.

- [ ] **Step 3: Update worker consumers**

Find and update every `app.llm` reference under `services/worker`:
```bash
grep -rn "app\.llm" services/worker
```
For each hit (at minimum `services/worker/app/pipeline/digest.py:7` — `from app.llm import ModelConfig, complete_structured`), replace `app.llm` → `gulp_shared.llm`. Include any worker test files.

- [ ] **Step 4: Add `anthropic` to the shared package deps**

In `services/shared/pyproject.toml`, add `anthropic` to `dependencies` (copy the exact version constraint from `services/worker/pyproject.toml`'s `anthropic` entry so the lockfile stays consistent):

```toml
dependencies = [
    "anthropic>=0.40",
    "pydantic-settings>=2.6",
    "sqlalchemy>=2.0",
]
```

(Use the worker's actual `anthropic` constraint if it differs from `>=0.40`.) Then sync:
```bash
uv sync
```

- [ ] **Step 5: Verify both suites are green**

Run:
```bash
cd services/worker && uv run pytest -q
cd ../api && uv run pytest -q
```
Expected: both PASS (worker's digest + any llm tests now import from `gulp_shared.llm`; api unaffected). If a worker test still references `app.llm`, fix it (Step 3 grep should have caught it).

- [ ] **Step 6: Commit**

```bash
git add services/shared/gulp_shared/llm services/shared/pyproject.toml \
        services/worker/app/pipeline/digest.py uv.lock
# plus any worker test files changed in Step 3:
git add services/worker/tests 2>/dev/null || true
git commit -m "refactor: relocate provider-agnostic LLM layer to gulp_shared"
```
(Stage only the moved package, the two pyproject/lock files, digest.py, and any worker test that changed — NOT the pre-existing WIP under services/shared/services/worker.)

---

### Task 2: `PackBlockMessage` model + migration

**Files:**
- Create: `services/shared/gulp_shared/models/pack_block_message.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Create: `services/api/alembic/versions/d3e4f5a6b7c8_s2_pack_block_messages.py`
- Test: `services/shared/tests/test_pack_block_message.py`

**Interfaces:**
- Produces: `PackBlockMessage(TimestampedBase, Base)` with `block_id: uuid (FK pack_blocks.id, ondelete CASCADE, indexed)`, `role: ChatRole`, `content: str`; `class ChatRole(str, enum.Enum): user; assistant`. Table `pack_block_messages`, enum `chat_role`.

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_pack_block_message.py`:

```python
import uuid

from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage


def test_pack_block_message_fields() -> None:
    m = PackBlockMessage(block_id=uuid.uuid4(), role=ChatRole.user, content="hi")
    assert m.role is ChatRole.user
    assert m.content == "hi"
    assert PackBlockMessage.__tablename__ == "pack_block_messages"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_pack_block_message.py -v`
Expected: FAIL — `No module named 'gulp_shared.models.pack_block_message'`.

- [ ] **Step 3: Create the model**

`services/shared/gulp_shared/models/pack_block_message.py`:

```python
"""PackBlockMessage — one turn of a per-block chat thread (S2 design §3.3/§3.4, S6 anchor)."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class PackBlockMessage(TimestampedBase, Base):
    __tablename__ = "pack_block_messages"

    block_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pack_blocks.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"))
    content: Mapped[str] = mapped_column(Text)
```

- [ ] **Step 4: Register the model for metadata/create_all**

In `services/shared/gulp_shared/models/__init__.py`, add the import and `__all__` entries (so `Base.metadata` and test `create_all` pick it up):

```python
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
```

and add `"PackBlockMessage"` and `"ChatRole"` to the `__all__` list.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_pack_block_message.py -v`
Expected: PASS.

- [ ] **Step 6: Hand-write the Alembic migration**

Create `services/api/alembic/versions/d3e4f5a6b7c8_s2_pack_block_messages.py` (hand-written — do NOT run `just migrate`/autogenerate, which would pick up unrelated WIP model edits):

```python
"""s2 pack block messages

Revision ID: d3e4f5a6b7c8
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa


revision = 'd3e4f5a6b7c8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pack_block_messages',
        sa.Column('block_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.Enum('user', 'assistant', name='chat_role'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['block_id'], ['pack_blocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_pack_block_messages_block_id'), 'pack_block_messages', ['block_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_pack_block_messages_block_id'), table_name='pack_block_messages')
    op.drop_table('pack_block_messages')
    op.execute("DROP TYPE IF EXISTS chat_role")
```

- [ ] **Step 7: Verify the migration parses + chains off the committed head**

Run:
```bash
cd services/api && uv run python -c "import importlib.util, pathlib; p='alembic/versions/d3e4f5a6b7c8_s2_pack_block_messages.py'; s=importlib.util.spec_from_file_location('m', p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.revision, m.down_revision)"
```
Expected: prints `d3e4f5a6b7c8 a1b2c3d4e5f6`. (Do NOT run `alembic upgrade head` — the untracked WIP migration `c2d3e4f5a6b7` also chains off `a1b2c3d4e5f6`, so Alembic will report multiple heads locally; that is a pre-existing WIP artifact, not this migration's problem.)

- [ ] **Step 8: Commit**

```bash
git add services/shared/gulp_shared/models/pack_block_message.py \
        services/shared/gulp_shared/models/__init__.py \
        services/shared/tests/test_pack_block_message.py \
        services/api/alembic/versions/d3e4f5a6b7c8_s2_pack_block_messages.py
git commit -m "feat(shared): PackBlockMessage model + migration"
```

---

### Task 3: Chat service — grounding + LLM answer + persistence

**Files:**
- Create: `services/api/app/services/chat.py`
- Test: `services/api/tests/test_block_chat.py`

**Interfaces:**
- Consumes: `load_block_scoped` (from `app.services.pack`, Phase 2a); `complete_structured`, `ModelConfig`, `LLMProvider` (from `gulp_shared.llm`, Task 1); `PackBlockMessage`/`ChatRole` (Task 2); `Source`, `KnowledgePack`, `PackSection`, `PackBlock`.
- Produces: `class ChatAnswer(BaseModel): answer: str`; `list_messages(db, snapshot_id, block_id) -> list[PackBlockMessage]` (raises `LookupError` if the block isn't under the snapshot); `async def answer_question(db, snapshot_id, block_id, question, *, provider: LLMProvider | None = None) -> PackBlockMessage` — persists the user turn, grounds + calls the LLM, persists + returns the assistant turn.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_block_chat.py`:

```python
import asyncio
import uuid
from typing import Any

import pytest

from app.services.chat import ChatAnswer, answer_question, list_messages
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_block_chat.py -v`
Expected: FAIL — `cannot import name 'answer_question' from 'app.services.chat'`.

- [ ] **Step 3: Implement the chat service**

Create `services/api/app/services/chat.py`:

```python
"""Per-block grounded chat: assemble context, call the LLM, persist the thread."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.pack import load_block_scoped
from gulp_shared.llm import LLMProvider, ModelConfig, complete_structured
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_block_message import ChatRole, PackBlockMessage
from gulp_shared.models.source import Source
from gulp_shared.settings import settings

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
    return (
        "You are helping the reader understand one block of a paper report. "
        "Answer the question grounded in the provided source and block; if the "
        "source does not cover it, say so plainly.\n"
        f"Report title: {pack.title if pack else ''}\n"
        f"Key insight: {pack.key_insight if pack else ''}\n"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_block_chat.py -v`
Expected: PASS (2 tests — persistence+grounding via `FakeProvider`, and the 404 scoping).

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/chat.py services/api/tests/test_block_chat.py
git commit -m "feat(api): grounded per-block chat service (persist + LLM answer)"
```

---

### Task 4: Messages endpoints + schemas

**Files:**
- Create: `services/api/app/schemas/chat.py`
- Modify: `services/api/app/routers/pack.py`
- Test: `services/api/tests/test_block_chat.py` (add endpoint tests)

**Interfaces:**
- Consumes: `list_messages`, `answer_question` (Task 3); `_owned_snapshot` (Phase 2a); `register_provider` (`gulp_shared.llm`, for the test to swap in a fake).
- Produces: `MessageOut { id: uuid, role: str, content: str, created_at: datetime }`; `MessageCreate { content: str }`. Routes `GET /snapshots/{snapshot_id}/blocks/{block_id}/messages` → `list[MessageOut]`; `POST` (async) same path, body `MessageCreate` → `MessageOut` (the assistant turn), `201`.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_block_chat.py` (extend imports with the TestClient fixture bits):

```python
from fastapi.testclient import TestClient
from app.deps import get_db
from app.main import app
from gulp_shared.llm import register_provider


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_block_chat.py::test_post_then_get_messages -v`
Expected: FAIL — route not defined (404/405) / `MessageOut` import error.

- [ ] **Step 3: Create the message schemas**

`services/api/app/schemas/chat.py`:

```python
"""Per-block chat contract — becomes the OpenAPI types the web client reads."""

import datetime
import uuid

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    content: str
```

- [ ] **Step 4: Add the routes**

In `services/api/app/routers/pack.py`, extend imports and add the two routes (the `_owned_snapshot` helper already exists from Phase 2a):

```python
from app.schemas.chat import MessageCreate, MessageOut
from app.services.chat import answer_question, list_messages
```

```python
@router.get(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    response_model=list[MessageOut],
)
def list_block_messages_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Any]:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return list_messages(db, snapshot_id, block_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found") from None


@router.post(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    response_model=MessageOut,
    status_code=201,
)
async def post_block_message_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return await answer_question(db, snapshot_id, block_id, body.content)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found") from None
```

Note: `MessageOut` is a Pydantic model with `from_attributes` implied by FastAPI's `response_model` serialization of ORM objects. If serialization fails because `from_attributes` isn't set, add `model_config = ConfigDict(from_attributes=True)` to `MessageOut` (and import `ConfigDict` from pydantic). Confirm via the test in Step 5.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_block_chat.py -v`
Expected: PASS (service tests + the two endpoint tests). If `MessageOut` failed to serialize the ORM row, apply the `from_attributes` note above and re-run.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/schemas/chat.py services/api/app/routers/pack.py \
        services/api/tests/test_block_chat.py
git commit -m "feat(api): per-block chat messages endpoints (GET/POST)"
```

---

### Task 5: Regenerate the client + typed chat helpers

**Files:**
- Regenerate: `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`
- Modify: `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: the two routes from Task 4.
- Produces (client): `MessageOut` type; `MessageCreateBody` type; `getBlockMessages(snapshotId, blockId): Promise<MessageOut[]>`; `postBlockMessage(snapshotId, blockId, body: MessageCreateBody): Promise<MessageOut>` — the helpers Phase 3b's ChatPanel calls.

- [ ] **Step 1: Regenerate the client**

Run: `just gen-client`
Expected: `schema.gen.ts` gains `get` + `post` on `/snapshots/{snapshot_id}/blocks/{block_id}/messages` and `MessageOut`/`MessageCreate` component schemas.

- [ ] **Step 2: Add the typed helpers**

Append to `packages/api-client/src/index.ts`:

```typescript
export type MessageOut =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}/messages"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MessageCreateBody =
  paths["/snapshots/{snapshot_id}/blocks/{block_id}/messages"]["post"]["requestBody"]["content"]["application/json"];

export async function getBlockMessages(
  snapshotId: string,
  blockId: string,
): Promise<MessageOut[]> {
  const { data, error } = await client.GET(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    { params: { path: { snapshot_id: snapshotId, block_id: blockId } }, cache: "no-store" },
  );
  if (error || !data) throw new Error("fetch block messages failed");
  return data;
}

export async function postBlockMessage(
  snapshotId: string,
  blockId: string,
  body: MessageCreateBody,
): Promise<MessageOut> {
  const { data, error } = await client.POST(
    "/snapshots/{snapshot_id}/blocks/{block_id}/messages",
    { params: { path: { snapshot_id: snapshotId, block_id: blockId } }, body },
  );
  if (error || !data) throw new Error("post block message failed");
  return data;
}
```

- [ ] **Step 3: Typecheck**

Run: `pnpm --filter @gulp/web exec tsc --noEmit`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/api-client/openapi.json packages/api-client/src/schema.gen.ts \
        packages/api-client/src/index.ts
git commit -m "feat(api-client): per-block chat message helpers"
```

---

## Self-Review

**Spec coverage (Phase 3 backend slice):**
- LLM layer relocated to `gulp_shared` (Decision B1) → Task 1. ✔
- `PackBlockMessage` model + migration → Task 2. ✔
- Grounded answer (block + section + pack title/key-insight + source excerpt, truncated) + persisted history → Task 3. ✔
- `GET`/`POST` messages endpoints, owner + pack scoped, async POST synchronous LLM → Task 4. ✔
- Client helpers → Task 5. ✔
- FakeProvider for hermetic tests (no real API) → Tasks 3–4 (`FakeProvider` + `register_provider` swap). ✔
- SSE streaming → deferred (plain request/response). ✔

**Placeholder scan:** every step has full code + exact commands. The one conditional (`from_attributes` on `MessageOut`) is a concrete, verifiable branch, not a placeholder.

**Type consistency:** `answer_question`/`list_messages` signatures (Task 3) are exactly what the routes call (Task 4). `ChatAnswer{answer}` matches the FakeProvider's returned `{"answer": ...}` and the real Anthropic tool-use output. `complete_structured(response_model=, messages=, system=, config=, provider=)` matches the relocated `gulp_shared.llm` signature (Task 1). `MessageOut`/`MessageCreate` (Task 4) → generated `MessageOut`/`MessageCreateBody` consumed as `getBlockMessages`/`postBlockMessage` (Task 5) — the names Phase 3b imports.

## Notes for Phase 3b (frontend — separate plan)

Consumes `getBlockMessages`/`postBlockMessage` + `MessageOut`. Builds: `ChatPanel` (loads history, sends a question with a loading state, close button); a `💬` on `BlockToolbar`; `PackReport` gains `selectedBlockId` state + a two-column workbench layout (reader left, docked `ChatPanel` right; `<1280px` → slide-over overlay per `docs/03 §5.2`).
