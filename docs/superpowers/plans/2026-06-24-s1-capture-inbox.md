# S1 Capture & Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one-gesture web capture of links and notes into a persisted `Snapshot` that lands in a derived Inbox, never blocking on AI — full stack, per `docs/subsystems/S1-capture-inbox-design.md`.

**Architecture:** Bottom-up across the repo's layers. `gulp_shared` gains the DB floor (`Base`/`engine`/`SessionLocal`) plus `User`/`Source`/`SourceTag` ORM models; `services/api` adds thin `POST /capture` + `GET /inbox` + `GET /snapshots/{id}` routers over a capture/inbox service layer, an auth stub, and an enqueue seam; `services/worker` registers a **no-op** `process_snapshot` (the S2 seam); `packages/api-client` regenerates from OpenAPI; `apps/web` adds a capture island (⌘K + ⊕ sheet) and a read-only Inbox, wiring the Sidebar count and Today peek to real data.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (**sync**, psycopg3), Postgres 17, Alembic, FastAPI, arq (Redis), pytest; TypeScript, Next.js App Router, `openapi-typescript` + `openapi-fetch`, vitest.

## Global Constraints

These apply to **every** task (copied verbatim from the spec / repo rules):

- **Capture never blocks on AI** (`04 §4 S1`): the `POST /capture` handler persists + **enqueues**, then returns — heavy work is never run inline.
- **Conventional layering** (`05 D4`): routers stay thin (parse → call service → return); business logic in `services/api/app/services`; persistence (ORM/db) only in `gulp_shared`.
- **The data model is the contract** (`04 §2.5`): Python schemas → OpenAPI → `packages/api-client`. After changing `app/schemas`, run `just gen-client`. The web app talks to the backend **only** through `@gulp/api-client`; never hand-write fetch types.
- **Single `Source` table + `kind` discriminator** (`02 D1`); S1 writes only `kind='snapshot'`. Fill only S1's columns; `emitted_by`/`pack_id` are deferred (their target tables don't exist).
- **`tags` is a join table** (`02 §2.3` / spec C7), never an array column.
- **Soft delete everywhere** (`02 §2.2`): every entity carries `id` (UUID), `created_at`, `updated_at`, `deleted_at`; nothing is hard-deleted.
- **Owner = the single seeded dev user** `DEV_USER_ID = 00000000-0000-0000-0000-000000000001` (spec C6); auth is a stub dependency.
- **Inbox is a derived view, never an entity** (`02 D3` / spec C4): `kind=snapshot AND deleted_at IS NULL AND status ≠ in_library` (the `no KBMembership` clause is added in S3 when that table exists).
- **Media types / captured_via in S1:** links → `media_type=webpage`; notes → `media_type=note`. `captured_via ∈ {paste, in_app, manual}`.
- **Use the `justfile`**, never the underlying tool when a recipe exists.

**Toolchain realities the tasks rely on:**
- The repo is **one uv workspace = one `.venv`**. Both `gulp-api` and `gulp-worker` expose a top-level `app` package, so api/worker test suites add their own service dir to `sys.path` (shown in their `conftest.py`) to import the *local* `app`.
- **Unit tests run on in-memory SQLite** (fast, no infra) — the models use cross-DB types (`sqlalchemy.Uuid`, `Enum`) so `Base.metadata.create_all` works there. The **Alembic migration targets Postgres** and is verified against `just up`.

---

## File Structure

**`services/shared/gulp_shared/`**
- `db/base.py` — `Base` (DeclarativeBase) + `TimestampedBase` mixin (id/created_at/updated_at/deleted_at)
- `db/session.py` — `engine`, `SessionLocal`
- `db/__init__.py` — re-export `Base`, `TimestampedBase`, `engine`, `SessionLocal`
- `models/user.py` — `User`, `Locale`, `DEV_USER_ID`
- `models/source.py` — `Source`, `SourceKind`, `SnapshotStatus`, `MediaType`, `CapturedVia`
- `models/source_tag.py` — `SourceTag`
- `models/__init__.py` — import all models (registers metadata)
- `domain/urls.py` — `normalize_url`
- `tests/conftest.py`, `tests/test_db.py`, `tests/test_models.py`, `tests/test_urls.py`

**`services/api/`**
- `alembic.ini`, `alembic/env.py`, `alembic/versions/*_s1.py` — migration + dev-user seed
- `app/core/auth.py` — `get_current_user`
- `app/core/queue.py` — `enqueue`
- `app/deps.py` — `get_db`, `get_enqueue` (modify)
- `app/schemas/capture.py` — `CaptureRequest`, `SnapshotOut`, `CaptureResponse`, `InboxOut`
- `app/services/capture.py` — `create_snapshot`
- `app/services/inbox.py` — `list_inbox`
- `app/services/snapshots.py` — `to_out`, `_tags_for`
- `app/routers/capture.py`, `app/routers/inbox.py`
- `app/main.py` — register routers (modify)
- `tests/conftest.py`, `tests/test_schemas.py`, `tests/test_capture.py`, `tests/test_inbox.py`, `tests/test_routers.py`

**`services/worker/`**
- `app/tasks/__init__.py` — `process_snapshot`, `WorkerSettings` (modify)
- `app/tasks/__main__.py` — boot arq (modify)
- `tests/test_tasks.py`

**`packages/api-client/`**
- `openapi.json` (generated), `src/schema.gen.ts` (generated)
- `src/index.ts` — typed client + helpers (modify)
- `package.json` — add `openapi-fetch` (modify)

**`apps/web/`**
- `vitest.config.ts`, `package.json` (add test deps + script)
- `lib/captureQueue.ts` + `lib/captureQueue.test.ts`
- `components/capture/CaptureProvider.tsx`, `CaptureSheet.tsx`, `CaptureSheet.module.css`, `CaptureButton.tsx`
- `components/shell/Shell.tsx` — mount provider + button (modify)
- `components/shell/Sidebar.tsx` — live Inbox count + route (modify)
- `app/inbox/page.tsx`, `components/inbox/InboxList.tsx`, `components/inbox/InboxRow.tsx`, `InboxRow.module.css`
- `app/page.tsx` — Today peek to real data (modify)
- `.env.example` (root, add `NEXT_PUBLIC_API_URL`)

---

## Task 1: Persistence floor + pytest setup

**Files:**
- Create: `services/shared/gulp_shared/db/base.py`, `services/shared/gulp_shared/db/session.py`
- Modify: `services/shared/gulp_shared/db/__init__.py` (currently empty)
- Modify: root `pyproject.toml` (add dev deps)
- Create: `services/shared/tests/conftest.py`, `services/shared/tests/test_db.py`

**Interfaces:**
- Produces: `gulp_shared.db.Base` (DeclarativeBase), `gulp_shared.db.TimestampedBase` (mixin: `id: uuid.UUID` PK, `created_at`/`updated_at: datetime`, `deleted_at: datetime | None`), `gulp_shared.db.engine`, `gulp_shared.db.SessionLocal` (sync `sessionmaker`).

- [ ] **Step 1: Add dev dependencies**

Ensure root `pyproject.toml` has a dev group with pytest + httpx (merge if a group already exists):

```toml
[dependency-groups]
dev = ["pytest>=8", "httpx>=0.28"]
```

Run: `uv sync`

- [ ] **Step 2: Write the failing test**

`services/shared/tests/conftest.py`:

```python
import pathlib
import sys

# gulp_shared is uniquely named, but keep the service dir importable for tests.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

`services/shared/tests/test_db.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class _Widget(TimestampedBase, Base):
    __tablename__ = "_widgets"
    name: Mapped[str] = mapped_column(String)


def test_timestamped_mixin_provides_implicit_fields():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    w = _Widget(name="x")
    session.add(w)
    session.commit()

    assert isinstance(w.id, uuid.UUID)
    assert isinstance(w.created_at, datetime)
    assert isinstance(w.updated_at, datetime)
    assert w.deleted_at is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_db.py -v`
Expected: FAIL — `ImportError: cannot import name 'Base' from 'gulp_shared.db'`

- [ ] **Step 4: Write the implementation**

`services/shared/gulp_shared/db/base.py`:

```python
"""Declarative base + the implicit fields every entity carries (docs/02 §2.2)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampedBase:
    """Mixin: id + created/updated/deleted timestamps on every table."""

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
```

`services/shared/gulp_shared/db/session.py`:

```python
"""Sync engine + session factory (docs/05 §4; driver from settings)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gulp_shared.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

`services/shared/gulp_shared/db/__init__.py` (replace the empty file):

```python
from gulp_shared.db.base import Base, TimestampedBase
from gulp_shared.db.session import SessionLocal, engine

__all__ = ["Base", "TimestampedBase", "SessionLocal", "engine"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/shared/gulp_shared/db services/shared/tests pyproject.toml uv.lock
git commit -m "feat(shared): db floor — Base, engine, SessionLocal, timestamped mixin"
```

---

## Task 2: ORM models (User, Source, SourceTag)

**Files:**
- Create: `services/shared/gulp_shared/models/user.py`, `models/source.py`, `models/source_tag.py`
- Modify: `services/shared/gulp_shared/models/__init__.py` (currently empty)
- Create: `services/shared/tests/test_models.py`

**Interfaces:**
- Consumes: `gulp_shared.db.Base`, `gulp_shared.db.TimestampedBase`.
- Produces:
  - `gulp_shared.models.user.User` (cols: `display_name: str | None`, `locale: Locale`), `Locale` enum (`zh`/`en`), `DEV_USER_ID: uuid.UUID`.
  - `gulp_shared.models.source.Source` (cols: `owner_id`, `kind`, `title`, `note`, `status`, `media_type`, `origin_url`, `content_body`, `content_ref`, `captured_via`) + enums `SourceKind`, `SnapshotStatus`, `MediaType`, `CapturedVia`.
  - `gulp_shared.models.source_tag.SourceTag` (cols: `source_id`, `tag`).

- [ ] **Step 1: Write the failing test**

`services/shared/tests/test_models.py`:

```python
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from gulp_shared.db import Base
import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.models.user import DEV_USER_ID, User


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_can_persist_a_snapshot_with_a_tag():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.processing,
        media_type=MediaType.webpage,
        origin_url="https://example.com/x",
        captured_via=CapturedVia.paste,
    )
    s.add(snap)
    s.flush()
    s.add(SourceTag(source_id=snap.id, tag="ml"))
    s.commit()

    got = s.scalar(select(Source).where(Source.owner_id == DEV_USER_ID))
    assert got is not None
    assert got.kind == SourceKind.snapshot
    assert got.status == SnapshotStatus.processing
    tag = s.scalar(select(SourceTag).where(SourceTag.source_id == snap.id))
    assert tag.tag == "ml"


def test_dev_user_id_is_the_fixed_uuid():
    assert DEV_USER_ID == uuid.UUID("00000000-0000-0000-0000-000000000001")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.models.user'`

- [ ] **Step 3: Write the implementation**

`services/shared/gulp_shared/models/user.py`:

```python
"""User — the account (docs/02 §4.1). S1 fills only what `owner` needs."""

import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Locale(str, enum.Enum):
    zh = "zh"
    en = "en"


class User(TimestampedBase, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(String, default=None)
    locale: Mapped[Locale] = mapped_column(Enum(Locale, name="locale"), default=Locale.en)
```

`services/shared/gulp_shared/models/source.py`:

```python
"""Source — single table + `kind` discriminator (docs/02 D1). S1 writes snapshots."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SourceKind(str, enum.Enum):
    snapshot = "snapshot"
    conversation = "conversation"
    subscription = "subscription"


class SnapshotStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    awaiting_review = "awaiting_review"
    in_library = "in_library"
    needs_attention = "needs_attention"


class MediaType(str, enum.Enum):
    article = "article"
    pdf = "pdf"
    video = "video"
    podcast = "podcast"
    note = "note"
    screenshot = "screenshot"
    audio = "audio"
    webpage = "webpage"


class CapturedVia(str, enum.Enum):
    share_sheet = "share_sheet"
    wechat = "wechat"
    email = "email"
    in_app = "in_app"
    paste = "paste"
    manual = "manual"
    screenshot = "screenshot"
    audio_memo = "audio_memo"


class Source(TimestampedBase, Base):
    __tablename__ = "sources"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind, name="source_kind"), index=True)
    title: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[SnapshotStatus] = mapped_column(
        Enum(SnapshotStatus, name="snapshot_status"), index=True
    )
    # snapshot-specific (docs/02 §4.3); nullable for other kinds.
    media_type: Mapped[MediaType | None] = mapped_column(
        Enum(MediaType, name="media_type"), default=None
    )
    origin_url: Mapped[str | None] = mapped_column(String, default=None, index=True)
    content_body: Mapped[str | None] = mapped_column(Text, default=None)
    content_ref: Mapped[str | None] = mapped_column(String, default=None)
    captured_via: Mapped[CapturedVia | None] = mapped_column(
        Enum(CapturedVia, name="captured_via"), default=None
    )
    # Deferred: `emitted_by` (S7), `pack_id` (S2) — target tables don't exist yet.
```

`services/shared/gulp_shared/models/source_tag.py`:

```python
"""Tags as a join (docs/02 §2.3) so membership unions under sync, not LWW-clobbers."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SourceTag(TimestampedBase, Base):
    __tablename__ = "source_tags"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    tag: Mapped[str] = mapped_column(String)
```

`services/shared/gulp_shared/models/__init__.py` (replace the empty file):

```python
from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.models.user import DEV_USER_ID, Locale, User

__all__ = [
    "User",
    "Locale",
    "DEV_USER_ID",
    "Source",
    "SourceKind",
    "SnapshotStatus",
    "MediaType",
    "CapturedVia",
    "SourceTag",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/shared/gulp_shared/models services/shared/tests/test_models.py
git commit -m "feat(shared): User, Source, SourceTag ORM models"
```

---

## Task 3: URL normalization

**Files:**
- Create: `services/shared/gulp_shared/domain/urls.py`
- Modify: `services/shared/gulp_shared/domain/__init__.py` (currently empty — leave as a namespace; no change needed)
- Create: `services/shared/tests/test_urls.py`

**Interfaces:**
- Produces: `gulp_shared.domain.urls.normalize_url(raw: str) -> str`.

- [ ] **Step 1: Write the failing test**

`services/shared/tests/test_urls.py`:

```python
from gulp_shared.domain.urls import normalize_url


def test_strips_fragment_tracking_and_trailing_slash_and_lowercases_host():
    a = normalize_url("https://A.com/Path/?utm_source=x&q=1#frag")
    b = normalize_url("https://a.com/Path?q=1")
    assert a == b == "https://a.com/Path?q=1"


def test_root_keeps_single_slash():
    assert normalize_url("http://a.com") == "http://a.com/"


def test_defaults_missing_scheme_to_https():
    assert normalize_url("a.com/x").startswith("https://a.com/x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_urls.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.domain.urls'`

- [ ] **Step 3: Write the implementation**

`services/shared/gulp_shared/domain/urls.py`:

```python
"""Canonicalize a URL for dedupe (spec C2). Pure; no network."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "ref", "ref_src"}


def normalize_url(raw: str) -> str:
    parts = urlsplit(raw.strip(), scheme="https")
    # urlsplit puts "a.com/x" into .path when no "//"; re-parse with a scheme prefix.
    if not parts.netloc:
        parts = urlsplit(f"https://{raw.strip()}")
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/") or "/"
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.lower().startswith(_TRACKING_PREFIXES) and k.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit((scheme, host, path, urlencode(kept), ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-shared pytest services/shared/tests/test_urls.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add services/shared/gulp_shared/domain/urls.py services/shared/tests/test_urls.py
git commit -m "feat(shared): normalize_url for capture dedupe"
```

---

## Task 4: Alembic migration + dev-user seed

**Files:**
- Create: `services/api/alembic.ini`, `services/api/alembic/env.py`, `services/api/alembic/script.py.mako`
- Create (generated, then edited): `services/api/alembic/versions/<rev>_s1_capture_inbox.py`

**Interfaces:**
- Consumes: `gulp_shared.db.Base`, `gulp_shared.models` (all tables), `gulp_shared.models.user.DEV_USER_ID`, `gulp_shared.settings.settings`.
- Produces: a Postgres schema with `users`, `sources`, `source_tags` and one seeded dev-user row.

> This task is verified by **integration** against Postgres (`just up`), not a unit test — it touches Alembic + a live DB.

- [ ] **Step 1: Start infra**

Run: `just up`
Expected: Postgres + Redis containers up.

- [ ] **Step 2: Write Alembic config**

`services/api/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

`services/api/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`services/api/alembic/env.py`:

```python
from alembic import context
from sqlalchemy import engine_from_config, pool

from gulp_shared.db import Base
from gulp_shared.settings import settings
import gulp_shared.models  # noqa: F401  (registers all tables on Base.metadata)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
```

- [ ] **Step 3: Autogenerate the migration**

Run: `just migrate "s1 capture inbox"`
Expected: a new file under `services/api/alembic/versions/` creating `users`, `sources`, `source_tags`.

- [ ] **Step 4: Add the dev-user seed**

Edit the generated migration: at the **end of `upgrade()`**, append the seed (keep the autogenerated `op.create_table` calls above it):

```python
    op.execute(
        "INSERT INTO users (id, display_name, locale, created_at, updated_at) "
        "VALUES ('00000000-0000-0000-0000-000000000001', 'Dev', 'en', now(), now())"
    )
```

- [ ] **Step 5: Apply and verify**

Run: `just migrate-up`
Then verify the dev user exists:

```bash
docker compose -f infra/docker-compose.yml exec -T db \
  psql -U gulp -d gulp -c "select id, display_name from users;"
```

Expected: one row, `00000000-0000-0000-0000-000000000001 | Dev`.

- [ ] **Step 6: Commit**

```bash
git add services/api/alembic.ini services/api/alembic
git commit -m "feat(api): alembic migration for S1 tables + dev-user seed"
```

---

## Task 5: API schemas (the contract)

**Files:**
- Create: `services/api/app/schemas/capture.py`
- Create: `services/api/tests/conftest.py`, `services/api/tests/test_schemas.py`

**Interfaces:**
- Consumes: `gulp_shared.models.source` enums.
- Produces:
  - `CaptureRequest` (`url: str | None`, `text: str | None`, `note: str | None`, `title: str | None`, `tags: list[str]`, `captured_via: CapturedVia`) — validator: **exactly one** of `url`/`text` non-empty.
  - `SnapshotOut` (`id`, `kind`, `title`, `note`, `status`, `media_type`, `origin_url`, `content_body`, `captured_via`, `tags: list[str]`, `created_at`, `updated_at`).
  - `CaptureResponse` (`snapshot: SnapshotOut`, `duplicate: bool`).
  - `InboxOut` (`items: list[SnapshotOut]`, `count: int`).

- [ ] **Step 1: Write the api test conftest**

`services/api/tests/conftest.py`:

```python
import pathlib
import sys

# Both gulp-api and gulp-worker expose a top-level `app`; put services/api first.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gulp_shared.db import Base
import gulp_shared.models  # noqa: F401
from gulp_shared.models.user import DEV_USER_ID, User


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(id=DEV_USER_ID, display_name="Dev"))
    session.commit()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Write the failing test**

`services/api/tests/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.schemas.capture import CaptureRequest


def test_accepts_a_url_only_request():
    req = CaptureRequest(url="https://a.com/x")
    assert req.url == "https://a.com/x"
    assert req.tags == []


def test_accepts_a_text_only_request():
    assert CaptureRequest(text="a thought").text == "a thought"


def test_rejects_both_url_and_text():
    with pytest.raises(ValidationError):
        CaptureRequest(url="https://a.com", text="also a note")


def test_rejects_neither():
    with pytest.raises(ValidationError):
        CaptureRequest(note="annotation only")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --package gulp-api pytest services/api/tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.capture'`

- [ ] **Step 4: Write the implementation**

`services/api/app/schemas/capture.py`:

```python
"""Request/response schemas — these become the OpenAPI contract (docs/05 §4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    SourceKind,
)


class CaptureRequest(BaseModel):
    url: str | None = None
    text: str | None = None  # note body
    note: str | None = None  # one-line annotation
    title: str | None = None
    tags: list[str] = []
    captured_via: CapturedVia = CapturedVia.in_app

    @model_validator(mode="after")
    def _exactly_one_of_url_or_text(self) -> "CaptureRequest":
        has_url = bool(self.url and self.url.strip())
        has_text = bool(self.text and self.text.strip())
        if has_url == has_text:
            raise ValueError("provide exactly one of `url` or `text`")
        return self


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    title: str
    note: str | None
    status: SnapshotStatus
    media_type: MediaType | None
    origin_url: str | None
    content_body: str | None
    captured_via: CapturedVia | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CaptureResponse(BaseModel):
    snapshot: SnapshotOut
    duplicate: bool


class InboxOut(BaseModel):
    items: list[SnapshotOut]
    count: int
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package gulp-api pytest services/api/tests/test_schemas.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add services/api/app/schemas/capture.py services/api/tests/conftest.py services/api/tests/test_schemas.py
git commit -m "feat(api): capture/inbox schemas (the OpenAPI contract)"
```

---

## Task 6: Core wiring — auth stub, enqueue, deps

**Files:**
- Create: `services/api/app/core/auth.py`, `services/api/app/core/queue.py`
- Modify: `services/api/app/deps.py`
- Modify: `services/api/pyproject.toml` (add `arq`)
- Create: `services/api/tests/test_auth.py`

**Interfaces:**
- Consumes: `gulp_shared.models.user.User`/`DEV_USER_ID`, `gulp_shared.db.SessionLocal`, `gulp_shared.settings.settings`.
- Produces:
  - `app.deps.get_db() -> Iterator[Session]`, `app.deps.get_enqueue() -> Callable[..., None]`.
  - `app.core.auth.get_current_user(db) -> User` (the seeded dev user).
  - `app.core.queue.enqueue(job_name: str, *args) -> None` (pushes to arq's Redis pool).

- [ ] **Step 1: Add arq to the API**

Edit `services/api/pyproject.toml` `dependencies` — add `"arq>=0.26",`. Run: `uv sync`

- [ ] **Step 2: Write the failing test**

`services/api/tests/test_auth.py`:

```python
from app.core.auth import get_current_user
from gulp_shared.models.user import DEV_USER_ID


def test_get_current_user_returns_the_seeded_dev_user(db):
    user = get_current_user(db=db)
    assert user.id == DEV_USER_ID
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --package gulp-api pytest services/api/tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.auth'`

- [ ] **Step 4: Write the implementation**

`services/api/app/core/queue.py`:

```python
"""The enqueue seam (spec C5). API is sync; bridge to arq's async pool."""

import asyncio

from arq import create_pool
from arq.connections import RedisSettings

from gulp_shared.settings import settings


def enqueue(job_name: str, *args: object) -> None:
    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job(job_name, *args)
        finally:
            await pool.aclose()

    asyncio.run(_go())
```

`services/api/app/core/auth.py`:

```python
"""Auth stub (spec C6): returns the seeded dev user. Swap for real sign-in (S0)."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from gulp_shared.models.user import DEV_USER_ID, User


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.get(User, DEV_USER_ID)
    if user is None:
        raise RuntimeError("dev user not seeded — run `just migrate-up`")
    return user
```

`services/api/app/deps.py` (replace the file):

```python
"""Shared FastAPI dependencies (db session, enqueue)."""

from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session

from app.core.queue import enqueue as _enqueue
from gulp_shared.db import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_enqueue() -> Callable[..., None]:
    return _enqueue
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package gulp-api pytest services/api/tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/api/app/core services/api/app/deps.py services/api/pyproject.toml services/api/tests/test_auth.py uv.lock
git commit -m "feat(api): auth stub, enqueue seam, db/enqueue deps"
```

---

## Task 7: Capture service + serializer

**Files:**
- Create: `services/api/app/services/capture.py`, `services/api/app/services/snapshots.py`
- Create: `services/api/tests/test_capture.py`

**Interfaces:**
- Consumes: `app.schemas.capture.CaptureRequest`/`SnapshotOut`, `gulp_shared.models.source`, `gulp_shared.models.source_tag.SourceTag`, `gulp_shared.domain.urls.normalize_url`.
- Produces:
  - `app.services.capture.create_snapshot(db: Session, owner_id: uuid.UUID, req: CaptureRequest, enqueue: Callable[..., None]) -> tuple[Source, bool]` (returns `(snapshot, duplicate)`).
  - `app.services.snapshots.to_out(db: Session, source: Source) -> SnapshotOut`, `_tags_for(db, source_id) -> list[str]`.

- [ ] **Step 1: Write the failing test**

`services/api/tests/test_capture.py`:

```python
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from gulp_shared.models.source import CapturedVia, MediaType, SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def _enqueue_spy():
    calls = []
    return calls, (lambda *a: calls.append(a))


def test_link_capture_creates_processing_webpage_and_enqueues(db):
    calls, enq = _enqueue_spy()
    snap, dup = create_snapshot(
        db,
        DEV_USER_ID,
        CaptureRequest(url="https://Example.com/x/?utm_source=z", captured_via=CapturedVia.paste),
        enq,
    )
    assert dup is False
    assert snap.media_type == MediaType.webpage
    assert snap.status == SnapshotStatus.processing
    assert snap.origin_url == "https://example.com/x"  # normalized
    assert snap.title == "example.com"  # host default
    assert calls == [("process_snapshot", str(snap.id))]


def test_note_capture_stores_body_and_does_not_enqueue_a_pack_for_url(db):
    calls, enq = _enqueue_spy()
    snap, dup = create_snapshot(
        db,
        DEV_USER_ID,
        CaptureRequest(text="first line\nsecond", captured_via=CapturedVia.manual),
        enq,
    )
    assert snap.media_type == MediaType.note
    assert snap.content_body == "first line\nsecond"
    assert snap.title == "first line"
    assert len(calls) == 1  # still enqueued (the seam runs for every fresh snapshot)


def test_duplicate_url_returns_existing_and_does_not_enqueue(db):
    calls, enq = _enqueue_spy()
    first, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p"), enq)
    again, dup = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/p?utm_x=1"), enq
    )
    assert dup is True
    assert again.id == first.id
    assert len(calls) == 1  # only the first enqueued


def test_tags_are_persisted_as_rows(db):
    from app.services.snapshots import _tags_for

    _, enq = _enqueue_spy()
    snap, _ = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/t", tags=["ml", "memory"]), enq
    )
    assert sorted(_tags_for(db, snap.id)) == ["memory", "ml"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-api pytest services/api/tests/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.capture'`

- [ ] **Step 3: Write the implementation**

`services/api/app/services/capture.py`:

```python
"""Capture business logic (docs/04 S1): create a Snapshot, dedupe, hand off."""

import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.capture import CaptureRequest
from gulp_shared.domain.urls import normalize_url
from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.source_tag import SourceTag

EnqueueFn = Callable[..., None]


def _host(url: str) -> str:
    return urlsplit(url).hostname or url


def create_snapshot(
    db: Session,
    owner_id: uuid.UUID,
    req: CaptureRequest,
    enqueue: EnqueueFn,
) -> tuple[Source, bool]:
    if req.url and req.url.strip():
        normalized = normalize_url(req.url)
        existing = db.scalar(
            select(Source).where(
                Source.owner_id == owner_id,
                Source.origin_url == normalized,
                Source.deleted_at.is_(None),
            )
        )
        if existing is not None:
            return existing, True
        source = Source(
            owner_id=owner_id,
            kind=SourceKind.snapshot,
            title=req.title or _host(normalized),
            note=req.note,
            status=SnapshotStatus.processing,
            media_type=MediaType.webpage,
            origin_url=normalized,
            captured_via=req.captured_via or CapturedVia.in_app,
        )
    else:
        text = (req.text or "").strip()
        default_title = text.splitlines()[0][:80] if text else "Untitled note"
        source = Source(
            owner_id=owner_id,
            kind=SourceKind.snapshot,
            title=req.title or default_title,
            note=req.note,
            status=SnapshotStatus.processing,
            media_type=MediaType.note,
            content_body=text,
            captured_via=req.captured_via or CapturedVia.manual,
        )

    db.add(source)
    db.flush()  # assign source.id
    for tag in req.tags:
        db.add(SourceTag(source_id=source.id, tag=tag))
    db.commit()
    db.refresh(source)

    # The S1↔S2 seam: hand off, never process inline (docs/04 S1).
    enqueue("process_snapshot", str(source.id))
    return source, False
```

`services/api/app/services/snapshots.py`:

```python
"""Serialize a Source (+ its tags) to the SnapshotOut contract."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.capture import SnapshotOut
from gulp_shared.models.source import Source
from gulp_shared.models.source_tag import SourceTag


def _tags_for(db: Session, source_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(SourceTag.tag).where(
                SourceTag.source_id == source_id,
                SourceTag.deleted_at.is_(None),
            )
        )
    )


def to_out(db: Session, source: Source) -> SnapshotOut:
    return SnapshotOut(
        id=source.id,
        kind=source.kind,
        title=source.title,
        note=source.note,
        status=source.status,
        media_type=source.media_type,
        origin_url=source.origin_url,
        content_body=source.content_body,
        captured_via=source.captured_via,
        tags=_tags_for(db, source.id),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-api pytest services/api/tests/test_capture.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/capture.py services/api/app/services/snapshots.py services/api/tests/test_capture.py
git commit -m "feat(api): capture service (create, dedupe, enqueue) + serializer"
```

---

## Task 8: Inbox service

**Files:**
- Create: `services/api/app/services/inbox.py`
- Create: `services/api/tests/test_inbox.py`

**Interfaces:**
- Produces: `app.services.inbox.list_inbox(db: Session, owner_id: uuid.UUID) -> list[Source]` — uncommitted, unfiled snapshots, newest first (spec C4).

- [ ] **Step 1: Write the failing test**

`services/api/tests/test_inbox.py`:

```python
from app.services.capture import create_snapshot
from app.schemas.capture import CaptureRequest
from app.services.inbox import list_inbox
from gulp_shared.models.source import SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def _noop(*a):
    return None


def test_inbox_lists_uncommitted_newest_first(db):
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"), _noop)
    b, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/2"), _noop)
    items = list_inbox(db, DEV_USER_ID)
    assert [i.id for i in items] == [b.id, a.id]  # newest first


def test_inbox_excludes_in_library_and_soft_deleted(db):
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/keep"), _noop)
    committed, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/done"), _noop)
    committed.status = SnapshotStatus.in_library
    db.commit()
    items = list_inbox(db, DEV_USER_ID)
    assert [i.id for i in items] == [a.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-api pytest services/api/tests/test_inbox.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.inbox'`

- [ ] **Step 3: Write the implementation**

`services/api/app/services/inbox.py`:

```python
"""The Inbox derived view (docs/02 D3 / spec C4). Never an entity — a query."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gulp_shared.models.source import SnapshotStatus, Source, SourceKind


def list_inbox(db: Session, owner_id: uuid.UUID) -> list[Source]:
    # `no KBMembership` clause arrives with S3 (the table doesn't exist yet).
    stmt = (
        select(Source)
        .where(
            Source.owner_id == owner_id,
            Source.kind == SourceKind.snapshot,
            Source.deleted_at.is_(None),
            Source.status != SnapshotStatus.in_library,
        )
        .order_by(Source.created_at.desc())
    )
    return list(db.scalars(stmt))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-api pytest services/api/tests/test_inbox.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/inbox.py services/api/tests/test_inbox.py
git commit -m "feat(api): inbox derived-view query"
```

---

## Task 9: Routers + app wiring

**Files:**
- Create: `services/api/app/routers/capture.py`, `services/api/app/routers/inbox.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/test_routers.py`

**Interfaces:**
- Consumes: services from Tasks 7–8, `app.deps.get_db`/`get_enqueue`, `app.core.auth.get_current_user`.
- Produces: HTTP `POST /capture` → `CaptureResponse`; `GET /snapshots/{snapshot_id}` → `SnapshotOut`; `GET /inbox` → `InboxOut`.

- [ ] **Step 1: Write the failing test**

`services/api/tests/test_routers.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.deps import get_db, get_enqueue
from app.main import app


@pytest.fixture
def client(db):
    calls = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def test_post_capture_creates_a_snapshot_and_returns_it(client):
    r = client.post("/capture", json={"url": "https://a.com/x", "captured_via": "paste"})
    assert r.status_code == 200
    body = r.json()
    assert body["duplicate"] is False
    assert body["snapshot"]["status"] == "processing"
    assert body["snapshot"]["media_type"] == "webpage"
    assert len(client.enqueue_calls) == 1


def test_post_capture_duplicate_url_flags_duplicate(client):
    client.post("/capture", json={"url": "https://a.com/dup"})
    r = client.post("/capture", json={"url": "https://a.com/dup?utm_x=1"})
    assert r.json()["duplicate"] is True


def test_get_inbox_lists_captures(client):
    client.post("/capture", json={"url": "https://a.com/1"})
    r = client.get("/inbox")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_get_snapshot_404_for_unknown_id(client):
    r = client.get("/snapshots/00000000-0000-0000-0000-0000000000ff")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-api pytest services/api/tests/test_routers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.capture'`

- [ ] **Step 3: Write the implementation**

`services/api/app/routers/capture.py`:

```python
"""Capture endpoints — thin (docs/05 D4): parse, call service, return."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import CaptureRequest, CaptureResponse, SnapshotOut
from app.services.capture import create_snapshot
from app.services.snapshots import to_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


@router.post("/capture", response_model=CaptureResponse)
def capture(
    req: CaptureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> CaptureResponse:
    source, duplicate = create_snapshot(db, user.id, req, enqueue)
    return CaptureResponse(snapshot=to_out(db, source), duplicate=duplicate)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SnapshotOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return to_out(db, source)
```

`services/api/app/routers/inbox.py`:

```python
"""Inbox endpoint — the derived view (spec C4)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.capture import InboxOut
from app.services.inbox import list_inbox
from app.services.snapshots import to_out
from gulp_shared.models.user import User

router = APIRouter()


@router.get("/inbox", response_model=InboxOut)
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InboxOut:
    sources = list_inbox(db, user.id)
    items = [to_out(db, s) for s in sources]
    return InboxOut(items=items, count=len(items))
```

`services/api/app/main.py` (replace the file):

```python
"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

from fastapi import FastAPI

from app.routers import capture, inbox

app = FastAPI(title="Gulp API")
app.include_router(capture.router, tags=["capture"])
app.include_router(inbox.router, tags=["inbox"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-api pytest services/api/tests/test_routers.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full API suite**

Run: `uv run --package gulp-api pytest services/api/tests -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/routers services/api/app/main.py services/api/tests/test_routers.py
git commit -m "feat(api): capture/inbox/snapshot routers wired into the app"
```

---

## Task 10: Worker placeholder (the S2 seam)

**Files:**
- Modify: `services/worker/app/tasks/__init__.py`, `services/worker/app/tasks/__main__.py`
- Create: `services/worker/tests/conftest.py`, `services/worker/tests/test_tasks.py`

**Interfaces:**
- Produces: `app.tasks.process_snapshot(ctx, snapshot_id: str) -> None` (no-op + log), `app.tasks.WorkerSettings` (registers the function).

- [ ] **Step 1: Write the worker test conftest + failing test**

`services/worker/tests/conftest.py`:

```python
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
```

`services/worker/tests/test_tasks.py`:

```python
import asyncio
import logging

from app.tasks import WorkerSettings, process_snapshot


def test_process_snapshot_is_a_noop_and_logs(caplog):
    with caplog.at_level(logging.INFO):
        asyncio.run(process_snapshot({}, "abc-123"))
    assert "abc-123" in caplog.text


def test_worker_registers_process_snapshot():
    assert process_snapshot in WorkerSettings.functions
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package gulp-worker pytest services/worker/tests -v`
Expected: FAIL — `ImportError: cannot import name 'WorkerSettings' from 'app.tasks'`

- [ ] **Step 3: Write the implementation**

`services/worker/app/tasks/__init__.py` (replace):

```python
"""Job definitions (arq). The queue the API enqueues into.

S1 ships a no-op `process_snapshot` — the seam S2 grows into the real pipeline
(fetch → parse → chunk → pack → draft cards → link concepts).
"""

import logging

from arq.connections import RedisSettings

from gulp_shared.settings import settings

logger = logging.getLogger("gulp.worker")


async def process_snapshot(ctx: dict, snapshot_id: str) -> None:
    logger.info("TODO(S2): process snapshot %s", snapshot_id)


class WorkerSettings:
    functions = [process_snapshot]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
```

`services/worker/app/tasks/__main__.py` (replace):

```python
"""`just worker` / `python -m app.tasks` entry. Boots the arq worker."""

from arq import run_worker

from app.tasks import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --package gulp-worker pytest services/worker/tests -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/tasks services/worker/tests
git commit -m "feat(worker): no-op process_snapshot placeholder (the S2 seam)"
```

---

## Task 11: Regenerate the API client

**Files:**
- Generated: `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`
- Modify: `packages/api-client/src/index.ts`, `packages/api-client/package.json`

**Interfaces:**
- Produces (from `@gulp/api-client`): `capture(body) -> Promise<CaptureResponse>`, `getInbox() -> Promise<InboxOut>`, `getSnapshot(id: string) -> Promise<SnapshotOut>`, plus `client` and a `Snapshot` type alias.

> Generation, then a thin typed wrapper. Verified by type-check, not a unit test.

- [ ] **Step 1: Add openapi-fetch**

Edit `packages/api-client/package.json` — add to a new `dependencies` block:

```json
  "dependencies": {
    "openapi-fetch": "^0.13.0"
  },
```

Run: `pnpm install`

- [ ] **Step 2: Generate the schema from the live API**

Run: `just gen-client`
Expected: `packages/api-client/openapi.json` and `packages/api-client/src/schema.gen.ts` written, listing `/capture`, `/inbox`, `/snapshots/{snapshot_id}`.

- [ ] **Step 3: Write the typed client**

`packages/api-client/src/index.ts` (replace the placeholder):

```ts
// The single contract surface between the Python API and the TS clients.
// `just gen-client` writes ./schema.gen.ts from the API's OpenAPI; the typed
// helpers below are the only thing apps import.
import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

const baseUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const client = createClient<paths>({ baseUrl });

export type CaptureBody =
  paths["/capture"]["post"]["requestBody"]["content"]["application/json"];
export type CaptureResponse =
  paths["/capture"]["post"]["responses"]["200"]["content"]["application/json"];
export type InboxOut =
  paths["/inbox"]["get"]["responses"]["200"]["content"]["application/json"];
export type Snapshot = InboxOut["items"][number];

export async function capture(body: CaptureBody): Promise<CaptureResponse> {
  const { data, error } = await client.POST("/capture", { body });
  if (error || !data) throw new Error("capture failed");
  return data;
}

export async function getInbox(): Promise<InboxOut> {
  const { data, error } = await client.GET("/inbox");
  if (error || !data) throw new Error("inbox fetch failed");
  return data;
}

export async function getSnapshot(id: string): Promise<Snapshot> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}", {
    params: { path: { snapshot_id: id } },
  });
  if (error || !data) throw new Error("snapshot fetch failed");
  return data;
}
```

- [ ] **Step 4: Type-check**

Run: `pnpm --filter @gulp/api-client exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add packages/api-client/package.json packages/api-client/openapi.json packages/api-client/src pnpm-lock.yaml
git commit -m "feat(api-client): generate S1 schema + typed capture/inbox helpers"
```

---

## Task 12: Web — env, vitest, offline capture queue

**Files:**
- Modify: root `.env.example` (add `NEXT_PUBLIC_API_URL`)
- Modify: `apps/web/package.json` (add vitest + jsdom + test script)
- Create: `apps/web/vitest.config.ts`, `apps/web/lib/captureQueue.ts`, `apps/web/lib/captureQueue.test.ts`

**Interfaces:**
- Consumes: `@gulp/api-client` `capture`, `CaptureBody`.
- Produces: `lib/captureQueue.ts` — `PendingCapture` type, `enqueuePending(item)`, `readQueue()`, `flushQueue(send?) -> Promise<number>`.

- [ ] **Step 1: Add the env var + vitest deps**

Append to root `.env.example`:

```
# --- Web client ---
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Edit `apps/web/package.json` — add to `devDependencies`: `"vitest": "^2.1.0"`, `"jsdom": "^25.0.0"`; add to `scripts`: `"test": "vitest run"`. Run: `pnpm install`

`apps/web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "jsdom" },
});
```

- [ ] **Step 2: Write the failing test**

`apps/web/lib/captureQueue.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { enqueuePending, flushQueue, readQueue } from "./captureQueue";

beforeEach(() => localStorage.clear());

describe("captureQueue", () => {
  it("persists and reads pending captures", () => {
    enqueuePending({ localId: "1", url: "https://a.com", tags: [], captured_via: "paste" });
    expect(readQueue()).toHaveLength(1);
  });

  it("flushes successes and keeps failures", async () => {
    enqueuePending({ localId: "1", url: "https://a.com", tags: [], captured_via: "paste" });
    enqueuePending({ localId: "2", url: "https://b.com", tags: [], captured_via: "paste" });

    const send = async (body: { url?: string }) => {
      if (body.url?.includes("b.com")) throw new Error("offline");
      return {} as never;
    };

    const flushed = await flushQueue(send);
    expect(flushed).toBe(1);
    expect(readQueue()).toHaveLength(1);
    expect(readQueue()[0].url).toContain("b.com");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter @gulp/web test`
Expected: FAIL — cannot find `./captureQueue`.

- [ ] **Step 4: Write the implementation**

`apps/web/lib/captureQueue.ts`:

```ts
// Thin offline-capture queue (spec C3): optimistic localStorage buffer that
// flushes on reconnect. Real reconciliation (dedupe-on-flush, cross-device
// merge) is S8 — not here.
import { capture as apiCapture, type CaptureBody } from "@gulp/api-client";

export type PendingCapture = {
  localId: string;
  url?: string;
  text?: string;
  note?: string;
  title?: string;
  tags: string[];
  captured_via: "paste" | "in_app" | "manual";
};

const KEY = "gulp.captureQueue";

export function readQueue(): PendingCapture[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]") as PendingCapture[];
  } catch {
    return [];
  }
}

function writeQueue(q: PendingCapture[]): void {
  localStorage.setItem(KEY, JSON.stringify(q));
}

export function enqueuePending(item: PendingCapture): void {
  writeQueue([...readQueue(), item]);
}

type Sender = (body: CaptureBody) => Promise<unknown>;

export async function flushQueue(send: Sender = apiCapture): Promise<number> {
  const queue = readQueue();
  const remaining: PendingCapture[] = [];
  let flushed = 0;
  for (const item of queue) {
    try {
      await send({
        url: item.url,
        text: item.text,
        note: item.note,
        title: item.title,
        tags: item.tags,
        captured_via: item.captured_via,
      });
      flushed += 1;
    } catch {
      remaining.push(item);
    }
  }
  writeQueue(remaining);
  return flushed;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter @gulp/web test`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add .env.example apps/web/package.json apps/web/vitest.config.ts apps/web/lib/captureQueue.ts apps/web/lib/captureQueue.test.ts pnpm-lock.yaml
git commit -m "feat(web): offline capture queue + vitest setup"
```

---

## Task 13: Web — capture island (⌘K + ⊕ sheet)

**Files:**
- Create: `apps/web/components/capture/CaptureProvider.tsx`, `CaptureSheet.tsx`, `CaptureSheet.module.css`, `CaptureButton.tsx`
- Modify: `apps/web/components/shell/Shell.tsx`

**Interfaces:**
- Consumes: `@gulp/api-client` `capture`; `lib/captureQueue` `enqueuePending`, `flushQueue`; `components/ui/Button`.
- Produces: `<CaptureProvider>` (context + ⌘K + reconnect flush), `useCapture()` hook (`open()`), `<CaptureButton>`.

> Client components; verified manually in the browser (no component-test runner in S1).

- [ ] **Step 1: Write CaptureProvider**

`apps/web/components/capture/CaptureProvider.tsx`:

```tsx
"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { flushQueue } from "@/lib/captureQueue";
import { CaptureSheet } from "./CaptureSheet";

type CaptureCtx = { open: () => void };
const Ctx = createContext<CaptureCtx | null>(null);

export function useCapture(): CaptureCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCapture must be used within CaptureProvider");
  return ctx;
}

export function CaptureProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const router = useRouter();
  const open = useCallback(() => setOpen(true), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    function onOnline() {
      void flushQueue().then((n) => {
        if (n > 0) router.refresh();
      });
    }
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [router]);

  return (
    <Ctx.Provider value={{ open }}>
      {children}
      {isOpen && <CaptureSheet onClose={() => setOpen(false)} />}
    </Ctx.Provider>
  );
}
```

> Note: `useCallback` is imported from `react` — fix the import to `import { createContext, useCallback, useContext, useEffect, useState } from "react";` (already shown). Verify there is no stray capitalization (`useCallback`, not `useCallBack`).

- [ ] **Step 2: Write CaptureSheet + styles**

`apps/web/components/capture/CaptureSheet.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { capture } from "@gulp/api-client";
import { enqueuePending } from "@/lib/captureQueue";
import { Button } from "@/components/ui/Button";
import styles from "./CaptureSheet.module.css";

type Mode = "link" | "note";

export function CaptureSheet({ onClose }: { onClose: () => void }) {
  const [mode, setMode] = useState<Mode>("link");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const router = useRouter();

  const canSave = mode === "link" ? url.trim().length > 0 : text.trim().length > 0;

  async function onSave() {
    const tags: string[] = [];
    const body =
      mode === "link"
        ? { url, title: title || undefined, tags, captured_via: "paste" as const }
        : { text, title: title || undefined, tags, captured_via: "manual" as const };
    onClose();
    try {
      await capture(body);
    } catch {
      enqueuePending({
        localId: crypto.randomUUID(),
        ...(mode === "link" ? { url } : { text }),
        title: title || undefined,
        tags,
        captured_via: mode === "link" ? "paste" : "manual",
      });
    }
    router.refresh();
  }

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.sheet} onClick={(e) => e.stopPropagation()}>
        <div className={styles.tabs}>
          <button
            className={mode === "link" ? styles.tabActive : styles.tab}
            onClick={() => setMode("link")}
          >
            Link
          </button>
          <button
            className={mode === "note" ? styles.tabActive : styles.tab}
            onClick={() => setMode("note")}
          >
            Note
          </button>
        </div>

        {mode === "link" ? (
          <input
            className={styles.input}
            placeholder="Paste a link…"
            autoFocus
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        ) : (
          <textarea
            className={styles.textarea}
            placeholder="Write a note…"
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}

        <input
          className={styles.input}
          placeholder="Title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <div className={styles.actions}>
          <span className={styles.target}>→ Inbox</span>
          <Button variant="primary" disabled={!canSave} onClick={onSave}>
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
```

`apps/web/components/capture/CaptureSheet.module.css`:

```css
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
  z-index: 50;
}
.sheet {
  width: min(560px, 92vw);
  background: var(--surface, #fff);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.tabs { display: flex; gap: 8px; }
.tab,
.tabActive {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border, #e3e3e3);
  background: transparent;
  cursor: pointer;
}
.tabActive { border-color: var(--accent, #2f6bff); color: var(--accent, #2f6bff); }
.input,
.textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border, #e3e3e3);
  border-radius: 8px;
  font: inherit;
}
.textarea { min-height: 120px; resize: vertical; }
.actions { display: flex; align-items: center; justify-content: space-between; }
.target { font-size: 13px; color: var(--text-muted, #777); }
```

- [ ] **Step 3: Write CaptureButton + mount in Shell**

`apps/web/components/capture/CaptureButton.tsx`:

```tsx
"use client";

import { Button } from "@/components/ui/Button";
import { useCapture } from "./CaptureProvider";

export function CaptureButton() {
  const { open } = useCapture();
  return (
    <Button variant="primary" onClick={open}>
      ⊕ Capture
    </Button>
  );
}
```

`apps/web/components/shell/Shell.tsx` (replace):

```tsx
import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { CaptureProvider } from "@/components/capture/CaptureProvider";
import { CaptureButton } from "@/components/capture/CaptureButton";
import styles from "./Shell.module.css";

// The web workbench frame (docs/03 §5.2): fixed sidebar + fluid content.
export function Shell({ children }: { children: ReactNode }) {
  return (
    <CaptureProvider>
      <div className={styles.shell}>
        <Sidebar />
        <main className={styles.main}>
          <div style={{ display: "flex", justifyContent: "flex-end", padding: "12px 24px 0" }}>
            <CaptureButton />
          </div>
          {children}
        </main>
      </div>
    </CaptureProvider>
  );
}
```

- [ ] **Step 4: Manual verification**

Run (three terminals or `just dev` after `just up` + `just migrate-up`): `just up`, `just migrate-up`, `just dev`.
In the browser at the web dev URL:
1. Press `⌘K` → the capture sheet opens.
2. Paste a URL, press Save → sheet closes (instant).
3. Click `⊕ Capture`, switch to Note, type text, Save → closes.
Expected: no errors in console; the API logs two `POST /capture` 200s and the worker logs two `TODO(S2): process snapshot …` lines.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/capture apps/web/components/shell/Shell.tsx
git commit -m "feat(web): capture island — Cmd-K + capture-confirm sheet"
```

---

## Task 14: Web — Inbox surface + wiring

**Files:**
- Create: `apps/web/app/inbox/page.tsx`, `apps/web/components/inbox/InboxList.tsx`, `apps/web/components/inbox/InboxRow.tsx`, `apps/web/components/inbox/InboxRow.module.css`
- Modify: `apps/web/components/shell/Sidebar.tsx`, `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: `@gulp/api-client` `getInbox`, `Snapshot`; `components/ui/ObjectGlyph`.

> Server components fetch at request time (spec §0 fork B1). Verified by the end-to-end manual check.

- [ ] **Step 1: Write the Inbox row + list**

`apps/web/components/inbox/InboxRow.tsx`:

```tsx
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import styles from "./InboxRow.module.css";

function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  return "Ready";
}

export function InboxRow({ item }: { item: Snapshot }) {
  const source = item.origin_url ? new URL(item.origin_url).host : "Note";
  return (
    <li className={styles.row}>
      <ObjectGlyph type="snapshot" />
      <div className={styles.text}>
        <span className={styles.title}>{item.title}</span>
        <span className={`t-data ${styles.meta}`}>{source}</span>
      </div>
      {item.origin_url && (
        <a className={styles.open} href={item.origin_url} target="_blank" rel="noreferrer">
          Open original
        </a>
      )}
      <span className={styles.status}>{statusLabel(item.status)}</span>
    </li>
  );
}
```

`apps/web/components/inbox/InboxList.tsx`:

```tsx
import type { Snapshot } from "@gulp/api-client";
import { InboxRow } from "./InboxRow";

export function InboxList({ items }: { items: Snapshot[] }) {
  if (items.length === 0) {
    return (
      <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>
        Nothing here yet — capture your first thing with ⌘K.
      </p>
    );
  }
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map((item) => (
        <InboxRow key={item.id} item={item} />
      ))}
    </ul>
  );
}
```

`apps/web/components/inbox/InboxRow.module.css`:

```css
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border, #eee);
}
.text { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
.title { font-weight: 500; }
.meta { color: var(--text-muted, #777); }
.open { font-size: 13px; color: var(--accent, #2f6bff); text-decoration: none; }
.status { font-size: 12px; color: var(--text-muted, #777); text-transform: lowercase; }
```

- [ ] **Step 2: Write the Inbox route**

`apps/web/app/inbox/page.tsx`:

```tsx
import { getInbox } from "@gulp/api-client";
import { InboxList } from "@/components/inbox/InboxList";

export const dynamic = "force-dynamic"; // always reflect the latest captures

export default async function InboxPage() {
  const inbox = await getInbox();
  return (
    <div style={{ padding: "24px" }}>
      <h1 className="t-title-l">Inbox</h1>
      <p className="t-data" style={{ color: "var(--text-muted, #777)", marginBottom: 16 }}>
        {inbox.count} awaiting
      </p>
      <InboxList items={inbox.items} />
    </div>
  );
}
```

- [ ] **Step 3: Wire the Sidebar Inbox row to the live count + route**

In `apps/web/components/shell/Sidebar.tsx`, make the component fetch the count and route Inbox. Replace the static `NAV` Inbox entry and the `<a>` rendering so the Inbox row links to `/inbox`. Concretely:
- Change the `Sidebar` function to `async`, fetch `const { count } = await getInbox();` at the top (add `import { getInbox } from "@gulp/api-client";`).
- In the `NAV` array, drop the hard-coded `count: 3` from the Inbox entry.
- In the `.map`, give the Inbox item `href="/inbox"` (others keep `href="#"`), and render `count` for Inbox as `{label === "Inbox" ? count : item.count}`.

Replace the `NAV` Inbox line:

```tsx
  { label: "Inbox", icon: IconInbox },
```

Replace the function signature and add the fetch:

```tsx
export async function Sidebar() {
  const { count } = await getInbox();
```

Replace the nav anchor to route Inbox + show the live count:

```tsx
        {NAV.map(({ label, icon: Glyph, active }) => (
          <a
            key={label}
            href={label === "Inbox" ? "/inbox" : "#"}
            className={`${styles.item} ${active ? styles.active : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Glyph className={styles.itemIcon} />
            <span className={styles.itemLabel}>{label}</span>
            {label === "Inbox" && count > 0 && (
              <span className={styles.itemCount}>{count}</span>
            )}
          </a>
        ))}
```

(Remove `count` from the `NavItem` type usage / `.map` destructure since it's no longer on the array.)

- [ ] **Step 4: Wire the Today recent-captures peek to real data**

In `apps/web/app/page.tsx`, replace the mock `today.recent` feed for the peek with live data while leaving the digest/start-gulp on mock:
- Add `import { getInbox } from "@gulp/api-client";` and make `TodayPage` `async`.
- Fetch `const inbox = await getInbox();` and map the first 3 items into the `CapturePeek` shape:

```tsx
  const recent = inbox.items.slice(0, 3).map((s) => ({
    id: s.id,
    type: "snapshot" as const,
    title: s.title,
    source: s.origin_url ? new URL(s.origin_url).host : "Note",
    time: "just now",
    status: (s.status === "needs_attention"
      ? "attention"
      : s.status === "ready"
        ? "ready"
        : "processing") as "ready" | "processing" | "attention",
  }));
```

- Pass `items={recent}` to `<CapturePeek />` instead of `today.recent`.

- [ ] **Step 5: End-to-end manual verification**

With `just up` + `just migrate-up` + `just dev` running:
1. Open the web app → Today. The "Recently captured" peek and the Sidebar Inbox count reflect real captures (0 on a fresh DB).
2. `⌘K` → paste a link → Save. Within a moment, the Sidebar Inbox count increments and the Today peek shows the item as **Processing**.
3. Click **Inbox** in the sidebar → `/inbox` lists the captured snapshot with **Open original**.
4. Capture the **same URL** again → still one item (dedupe; the second `POST /capture` returns `duplicate: true`).
5. Capture a **Note** → it appears in Inbox with source "Note".

Expected: every capture is instant; the worker logs `TODO(S2)` per fresh snapshot; duplicates don't add rows.

- [ ] **Step 6: Run all automated suites + lint**

Run:
```bash
uv run --package gulp-shared pytest services/shared/tests -q
uv run --package gulp-api pytest services/api/tests -q
uv run --package gulp-worker pytest services/worker/tests -q
pnpm --filter @gulp/web test
just lint
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/inbox apps/web/components/inbox apps/web/components/shell/Sidebar.tsx apps/web/app/page.tsx
git commit -m "feat(web): Inbox surface + live Sidebar count + Today peek"
```

---

## Self-Review

**Spec coverage (`docs/subsystems/S1-capture-inbox-design.md`):**
- §2 C1 capture targets (link+note) → Tasks 5, 7, 13. ✅
- §2 C2 URL dedupe + "open existing" → Task 3 (normalize), Task 7 (lookup), Task 14 (Open original / dedup behavior). ✅
- §2 C3 offline queue → Task 12 (queue) + Task 13 (enqueue on failure, flush on reconnect). ✅
- §2 C4 Inbox derived view → Task 8 (query) + Task 14 (surface). ✅
- §2 C5 enqueue seam + no-op worker → Task 6 (enqueue), Task 7 (call), Task 10 (placeholder). ✅
- §2 C6 dev-user auth stub → Task 4 (seed), Task 6 (auth). ✅
- §2 C7 tags as join → Task 2 (model) + Task 7 (persist) + Task 7 serializer. ✅
- §5 data layer (db floor, User/Source/SourceTag, normalize_url, migration+seed) → Tasks 1–4. ✅
- §6 API (auth, queue, schemas, capture/inbox/serialize services, routers) → Tasks 5–9. ✅
- §7 worker seam → Task 10. ✅
- §8 web (api-client, capture island, Inbox, offline, sidebar+today wiring) → Tasks 11–14. ✅
- §9 cross-cutting states: Loading/Processing/Empty surfaced in Task 14 (empty state, status label); Offline in Tasks 12–13. `needs_attention` UI kept ready (status label) though unreachable in S1. ✅
- §10 acceptance: instant confirm (Task 9 returns before worker), appears in Inbox (Task 14 e2e), dedupe (Tasks 7/14), offline (Tasks 12/13). ✅

**Placeholder scan:** no "TBD/handle errors/similar to" — every code step shows complete code. The literal string `TODO(S2)` is intentional product content (the worker's log line / the S2 seam), not a plan gap. ✅

**Type consistency:** `create_snapshot(db, owner_id, req, enqueue) -> tuple[Source, bool]` consumed identically in Tasks 8/9 tests and the router. `to_out(db, source)` / `_tags_for(db, source_id)` consistent across capture/inbox routers. `enqueue("process_snapshot", str(id))` matches `process_snapshot(ctx, snapshot_id: str)` in Task 10. `CaptureBody`/`CaptureResponse`/`InboxOut`/`Snapshot` names from Task 11 reused verbatim in Tasks 12–14. ✅
