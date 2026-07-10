# User System (S0 real sign-in) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded dev-user auth stub with a real email+password account system so anyone can register, log in, and see only their own data.

**Architecture:** Opaque server-side sessions (random token in Redis) carried in an httpOnly cookie. The single `get_current_user` dependency — which every router already depends on — is rewritten to resolve the cookie to a user, so the whole API becomes multi-user in one edit. The Next.js web app talks to the API same-origin through a `/api/*` rewrite (first-party cookie); server-component renders forward the incoming cookie to the API.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Redis (Python 3.13, uv); argon2-cffi for hashing; Next.js 15 App Router + React 19 + CSS Modules + openapi-fetch (TypeScript, pnpm); vitest.

**Spec:** `docs/superpowers/specs/2026-07-10-user-system-design.md`

## Global Constraints

- **Python ≥ 3.13**, mypy **strict** (excludes `tests/` and `alembic/`); ruff `select = E,F,I,UP,B`, line-length 100.
- **Run Python tests per-package:** `cd services/api && uv run pytest` and `cd services/shared && uv run pytest`. Repo-root pytest collides on the api-vs-worker `app` namespace — never run it.
- **Web vitest uses the classic JSX transform:** every JSX-bearing file (components AND tests) must `import React`; JSX-free files must not.
- **The data model is the contract:** after any API schema change, run `just gen-client` (regenerates `packages/api-client/schema.gen.ts`). `schema.gen.ts` has 2 pre-existing duplicate-identifier `tsc` errors (cards/job HEAD+GET) — `just lint` runs eslint, not tsc, so ignore them when checking types.
- **Keep `just lint` green** (ruff + mypy-per-service + eslint) and `just test` green before every commit that closes a task.
- **English** for all code/comments/commits/docs. UI copy is bilingual eventually, but the web app has **no i18n framework** — the entire existing UI is English string literals, so auth UI copy is English too (the account still stores a `locale`; app-wide i18n is a separate future effort).
- **Alembic head is `033e0b57ef69`** (`reader_chat_pack_messages`). The new migration's `down_revision` is this.
- **Dev account:** `DEV_USER_ID = 00000000-0000-0000-0000-000000000001`; after migration it logs in as `dev@gulp.local` with password `gulp-dev-2026` (documented in `.env.example`).
- **api-client** package is `@gulp/api-client`, consumed as raw TS source (no build); imported via named exports.
- **Session cookie name is `gulp_session`** (must match between API `settings.session_cookie_name` and web middleware).
- Commit after each task. TDD: test first, watch it fail, implement, watch it pass.

---

## Task 1: Password hashing + session-token primitives

**Files:**
- Modify: `services/api/pyproject.toml` (add `argon2-cffi` runtime dep)
- Create: `services/api/app/core/security.py`
- Test: `services/api/tests/test_security.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, password_hash: str) -> bool`, `new_session_token() -> str`.

- [ ] **Step 1: Add the dependency**

In `services/api/pyproject.toml`, add to `dependencies` (keep the list sorted-ish, after `arq`):

```toml
    "argon2-cffi>=23",
```

Then install: `uv sync`
Expected: resolves and installs `argon2-cffi`.

- [ ] **Step 2: Write the failing test**

Create `services/api/tests/test_security.py`:

```python
from app.core.security import hash_password, new_session_token, verify_password


def test_hash_password_round_trips() -> None:
    h = hash_password("s3cret-password")
    assert h != "s3cret-password"
    assert h.startswith("$argon2id$")
    assert verify_password("s3cret-password", h) is True


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("s3cret-password")
    assert verify_password("wrong", h) is False


def test_verify_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-hash") is False


def test_new_session_token_is_unique_and_long() -> None:
    a, b = new_session_token(), new_session_token()
    assert a != b
    assert len(a) >= 32
```

- [ ] **Step 3: Run it, verify it fails**

Run: `cd services/api && uv run pytest tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.security'`.

- [ ] **Step 4: Implement**

Create `services/api/app/core/security.py`:

```python
"""Password hashing (argon2id) + opaque session-token minting (spec 2026-07-10 §D2/§5.2)."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> str:
    """URL-safe opaque token; ~43 chars for 32 bytes of entropy."""
    return secrets.token_urlsafe(32)
```

- [ ] **Step 5: Run tests + lint, verify pass**

Run: `cd services/api && uv run pytest tests/test_security.py -v`
Expected: 4 passed.
Run: `just lint`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add services/api/pyproject.toml services/api/app/core/security.py services/api/tests/test_security.py uv.lock
git commit -m "feat(api): argon2id password hashing + session-token primitives"
```

---

## Task 2: User credentials + concept ownership (shared models)

**Files:**
- Modify: `services/shared/gulp_shared/models/user.py`
- Modify: `services/shared/gulp_shared/models/concept.py`
- Modify: `services/shared/tests/test_concept_models.py` (pass `owner_id`)
- Modify: `services/api/tests/test_delete_snapshot.py` (pass `owner_id`)
- Test: `services/shared/tests/test_user_model.py`

**Interfaces:**
- Produces: `User.email: str` (unique), `User.password_hash: str`; `Concept.owner_id: uuid.UUID`, `ConceptEdge.owner_id: uuid.UUID`.
- Note: `email`/`password_hash` carry model-level defaults so the ~40 existing `User(...)` test/seed sites keep working — the defaults only ever fire for test/seed rows; `register` always sets both explicitly. `Concept.owner_id` has NO default (defaulting it would undermine isolation) — its 2 construction sites are updated here.

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_user_model.py`:

```python
import uuid

import pytest
from gulp_shared.db import Base
from gulp_shared.models.user import User
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_email_is_unique() -> None:
    s = _session()
    s.add(User(email="a@example.com", password_hash="x"))
    s.commit()
    s.add(User(email="a@example.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        s.commit()


def test_bare_user_gets_defaults() -> None:
    # ~40 test sites construct User() without credentials — defaults keep them valid.
    s = _session()
    u = User(id=uuid.uuid4())
    s.add(u)
    s.commit()
    assert u.email is not None
    assert u.password_hash is not None
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd services/shared && uv run pytest tests/test_user_model.py -v`
Expected: FAIL — `TypeError`/`AttributeError` (no `email`/`password_hash`).

- [ ] **Step 3: Add credentials to User**

In `services/shared/gulp_shared/models/user.py`, replace the class body. Add the import for `uuid` (already present) and set the two new columns first:

```python
class User(TimestampedBase, Base):
    __tablename__ = "users"

    # Identity/credentials (spec 2026-07-10). Defaults fire only for test/seed
    # rows — `register` always sets both explicitly; prod emails are all real.
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, default=lambda: f"user-{uuid.uuid4()}@example.invalid"
    )
    password_hash: Mapped[str] = mapped_column(String, default="")
    display_name: Mapped[str | None] = mapped_column(String, default=None)
    locale: Mapped[Locale] = mapped_column(Enum(Locale, name="locale"), default=Locale.en)
    gulp_session_minutes: Mapped[int] = mapped_column(default=5)
```

- [ ] **Step 4: Add owner_id to the concept graph**

In `services/shared/gulp_shared/models/concept.py`, add `owner_id` to both `Concept` and `ConceptEdge` (import `ForeignKey` already present):

```python
class Concept(TimestampedBase, Base):
    __tablename__ = "concepts"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    concept_type: Mapped[ConceptType] = mapped_column(Enum(ConceptType, name="concept_type"))
    name: Mapped[str] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    definition: Mapped[str | None] = mapped_column(Text, default=None)


class ConceptEdge(TimestampedBase, Base):
    __tablename__ = "concept_edges"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    from_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    to_concept_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("concepts.id"), index=True)
    relation: Mapped[ConceptRelation] = mapped_column(Enum(ConceptRelation, name="concept_relation"))
    weight: Mapped[float | None] = mapped_column(Float, default=None)
```

- [ ] **Step 5: Fix the 2 concept construction sites**

In `services/shared/tests/test_concept_models.py`, the test seeds a dev user at line ~26 (`s.add(User(id=DEV_USER_ID, display_name="Dev"))`). Pass `owner_id=DEV_USER_ID` to the concepts/edge (import `DEV_USER_ID` from `gulp_shared.models.user` if not already):

```python
    a = Concept(owner_id=DEV_USER_ID, concept_type=ConceptType.term, name="Transformer", aliases=["xformer"])
    b = Concept(owner_id=DEV_USER_ID, concept_type=ConceptType.idea, name="Attention")
    s.add_all([a, b])
    s.flush()
    s.add(ConceptEdge(owner_id=DEV_USER_ID, from_concept_id=a.id, to_concept_id=b.id, relation=ConceptRelation.part_of))
```

In `services/api/tests/test_delete_snapshot.py:82`, add `owner_id` (use the owner already in scope — inspect the test; it seeds the dev user, so `owner_id=DEV_USER_ID` or the local `owner.id`):

```python
    concept = Concept(owner_id=DEV_USER_ID, concept_type=ConceptType.term, name="c")
```

- [ ] **Step 6: Run tests, verify pass**

Run: `cd services/shared && uv run pytest -q`
Expected: all pass (including new `test_user_model.py` and existing `test_concept_models.py`).
Run: `cd services/api && uv run pytest tests/test_delete_snapshot.py -q`
Expected: pass.
Run: `just lint`
Expected: green.

- [ ] **Step 7: Commit**

```bash
git add services/shared/gulp_shared/models/user.py services/shared/gulp_shared/models/concept.py services/shared/tests/ services/api/tests/test_delete_snapshot.py
git commit -m "feat(shared): User email/password_hash + owner_id on concept graph"
```

---

## Task 3: Alembic migration (users credentials, dev backfill, concept owner_id) + settings

**Files:**
- Modify: `services/shared/gulp_shared/settings.py`
- Modify: `.env.example`
- Create: `services/api/alembic/versions/<rev>_user_system.py`

**Interfaces:**
- Produces settings: `session_ttl_days: int`, `session_cookie_name: str`, `session_cookie_secure: bool`, `login_max_attempts: int`, `login_lockout_seconds: int`.

- [ ] **Step 1: Add settings**

In `services/shared/gulp_shared/settings.py`, add fields to `Settings` (after `auth_secret`):

```python
    session_ttl_days: int = 30
    session_cookie_name: str = "gulp_session"
    session_cookie_secure: bool = False  # True in production (HTTPS)
    login_max_attempts: int = 10
    login_lockout_seconds: int = 900
```

- [ ] **Step 2: Document env**

In `.env.example`, under the Auth section, add:

```bash
# Session cookie is Secure in production only (HTTPS). Set true when deployed.
SESSION_COOKIE_SECURE=false
# Seeded dev account after `just migrate-up`: dev@gulp.local / gulp-dev-2026
```

- [ ] **Step 3: Write the migration**

Create `services/api/alembic/versions/a9b0c1d2e3f4_user_system.py` (pick any unused 12-hex revision id; keep the filename slug `user_system`):

```python
"""user system: users email/password_hash (+ dev backfill), concept owner_id

Revision ID: a9b0c1d2e3f4
Revises: 033e0b57ef69
"""

import sqlalchemy as sa
from alembic import op
from argon2 import PasswordHasher

revision = "a9b0c1d2e3f4"
down_revision = "033e0b57ef69"
branch_labels = None
depends_on = None

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
DEV_EMAIL = "dev@gulp.local"
DEV_PASSWORD = "gulp-dev-2026"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. users: add credentials nullable, backfill, then enforce.
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=True))
    conn.execute(
        sa.text("UPDATE users SET email = :e, password_hash = :h WHERE id = :id"),
        {"e": DEV_EMAIL, "h": PasswordHasher().hash(DEV_PASSWORD), "id": DEV_USER_ID},
    )
    # Defensive: any other pre-existing user rows get a placeholder (cannot log in).
    conn.execute(
        sa.text(
            "UPDATE users SET email = 'user-' || id || '@example.invalid' WHERE email IS NULL"
        )
    )
    conn.execute(sa.text("UPDATE users SET password_hash = '' WHERE password_hash IS NULL"))
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "password_hash", nullable=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. concept graph: add owner_id nullable, backfill to dev user, enforce + FK.
    for table in ("concepts", "concept_edges"):
        op.add_column(table, sa.Column("owner_id", sa.Uuid(), nullable=True))
        conn.execute(sa.text(f"UPDATE {table} SET owner_id = :id WHERE owner_id IS NULL"), {"id": DEV_USER_ID})
        op.alter_column(table, "owner_id", nullable=False)
        op.create_index(op.f(f"ix_{table}_owner_id"), table, ["owner_id"])
        op.create_foreign_key(f"fk_{table}_owner_id", table, "users", ["owner_id"], ["id"])


def downgrade() -> None:
    for table in ("concept_edges", "concepts"):
        op.drop_constraint(f"fk_{table}_owner_id", table, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table}_owner_id"), table_name=table)
        op.drop_column(table, "owner_id")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
```

- [ ] **Step 4: Apply and verify**

Ensure infra is up (`just up`), then:
Run: `just migrate-up`
Expected: upgrades to `a9b0c1d2e3f4` with no error.
Verify the dev user:

```bash
just psql -c "SELECT email, left(password_hash, 12) FROM users WHERE id = '00000000-0000-0000-0000-000000000001';"
```

(If there is no `just psql` recipe, use `psql "$DATABASE_URL" -c "..."`.)
Expected: one row, `email = dev@gulp.local`, `password_hash` starting `$argon2id$`.

- [ ] **Step 5: Commit**

```bash
git add services/shared/gulp_shared/settings.py .env.example services/api/alembic/versions/a9b0c1d2e3f4_user_system.py
git commit -m "feat(api): migration — user credentials + dev backfill + concept owner_id"
```

---

## Task 4: Redis session store + login throttle + injectable redis

**Files:**
- Modify: `pyproject.toml` (add `fakeredis` dev dep)
- Modify: `services/api/app/deps.py` (add `get_redis`)
- Create: `services/api/app/core/sessions.py`
- Create: `services/api/app/core/throttle.py`
- Test: `services/api/tests/test_sessions.py`

**Interfaces:**
- Produces: `get_redis() -> redis.Redis[str]`; `SessionStore` protocol + `RedisSessionStore`; `get_sessions(r=Depends(get_redis)) -> SessionStore` with `.create(user_id)->str`, `.resolve(token)->uuid.UUID|None`, `.revoke(token)`, `.revoke_all(user_id)`; `LoginThrottle` with `.is_locked(key)->bool`, `.record_failure(key)`, `.reset(key)`, and `get_throttle(r=Depends(get_redis)) -> LoginThrottle`.

- [ ] **Step 1: Add the test dependency**

In root `pyproject.toml`, add to `[dependency-groups].dev`:

```toml
    "fakeredis>=2.26",
```

Run: `uv sync`

- [ ] **Step 2: Write the failing test**

Create `services/api/tests/test_sessions.py`:

```python
import uuid

import fakeredis
import pytest
from app.core.sessions import RedisSessionStore
from app.core.throttle import LoginThrottle


@pytest.fixture
def r():  # type: ignore[no-untyped-def]
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_create_resolve_round_trip(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    token = store.create(uid)
    assert store.resolve(token) == uid


def test_resolve_unknown_token_is_none(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    assert store.resolve("nope") is None


def test_revoke_kills_the_session(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    token = store.create(uid)
    store.revoke(token)
    assert store.resolve(token) is None


def test_revoke_all_kills_every_session_for_user(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    t1, t2 = store.create(uid), store.create(uid)
    store.revoke_all(uid)
    assert store.resolve(t1) is None
    assert store.resolve(t2) is None


def test_throttle_locks_after_max(r) -> None:  # type: ignore[no-untyped-def]
    throttle = LoginThrottle(r, max_attempts=3, window_seconds=900)
    assert throttle.is_locked("k") is False
    for _ in range(3):
        throttle.record_failure("k")
    assert throttle.is_locked("k") is True
    throttle.reset("k")
    assert throttle.is_locked("k") is False
```

- [ ] **Step 3: Run it, verify it fails**

Run: `cd services/api && uv run pytest tests/test_sessions.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 4: Add `get_redis` to deps**

In `services/api/app/deps.py`, add:

```python
import redis
from gulp_shared.settings import settings

_redis: "redis.Redis[str] | None" = None


def get_redis() -> "redis.Redis[str]":
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
```

- [ ] **Step 5: Implement the session store**

Create `services/api/app/core/sessions.py` (all imports at top — ruff E402 forbids mid-file imports):

```python
"""Server-side session store (spec 2026-07-10 §5.2). Opaque tokens in Redis;
the cookie carries the token, never user data. Revocable per-token and per-user."""

import uuid
from typing import Protocol

import redis
from fastapi import Depends
from gulp_shared.settings import settings

from app.core.security import new_session_token
from app.deps import get_redis


class SessionStore(Protocol):
    def create(self, user_id: uuid.UUID) -> str: ...
    def resolve(self, token: str) -> uuid.UUID | None: ...
    def revoke(self, token: str) -> None: ...
    def revoke_all(self, user_id: uuid.UUID) -> None: ...


class RedisSessionStore:
    def __init__(self, client: "redis.Redis[str]", ttl_seconds: int) -> None:
        self._r = client
        self._ttl = ttl_seconds

    def create(self, user_id: uuid.UUID) -> str:
        token = new_session_token()
        self._r.set(f"session:{token}", str(user_id), ex=self._ttl)
        self._r.sadd(f"user_sessions:{user_id}", token)
        return token

    def resolve(self, token: str) -> uuid.UUID | None:
        raw = self._r.get(f"session:{token}")
        if raw is None:
            return None
        self._r.expire(f"session:{token}", self._ttl)  # sliding TTL
        return uuid.UUID(str(raw))

    def revoke(self, token: str) -> None:
        raw = self._r.get(f"session:{token}")
        self._r.delete(f"session:{token}")
        if raw is not None:
            self._r.srem(f"user_sessions:{raw}", token)

    def revoke_all(self, user_id: uuid.UUID) -> None:
        key = f"user_sessions:{user_id}"
        for token in self._r.smembers(key):
            self._r.delete(f"session:{token}")
        self._r.delete(key)


def get_sessions(r: "redis.Redis[str]" = Depends(get_redis)) -> SessionStore:
    return RedisSessionStore(r, settings.session_ttl_days * 86400)
```

- [ ] **Step 6: Implement the throttle**

Create `services/api/app/core/throttle.py` (imports at top):

```python
"""Fixed-window login throttle (spec 2026-07-10 §5.5). Keyed by email+IP."""

import redis
from fastapi import Depends
from gulp_shared.settings import settings

from app.deps import get_redis


class LoginThrottle:
    def __init__(self, client: "redis.Redis[str]", max_attempts: int, window_seconds: int) -> None:
        self._r = client
        self._max = max_attempts
        self._window = window_seconds

    def is_locked(self, key: str) -> bool:
        raw = self._r.get(f"login_fail:{key}")
        return raw is not None and int(raw) >= self._max

    def record_failure(self, key: str) -> None:
        k = f"login_fail:{key}"
        count = self._r.incr(k)
        if count == 1:
            self._r.expire(k, self._window)

    def reset(self, key: str) -> None:
        self._r.delete(f"login_fail:{key}")


def get_throttle(r: "redis.Redis[str]" = Depends(get_redis)) -> LoginThrottle:
    return LoginThrottle(r, settings.login_max_attempts, settings.login_lockout_seconds)
```

- [ ] **Step 7: Run tests + lint, verify pass**

Run: `cd services/api && uv run pytest tests/test_sessions.py -v`
Expected: 5 passed.
Run: `just lint`
Expected: green (mypy strict clean — note the `redis.Redis[str]` annotations).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock services/api/app/deps.py services/api/app/core/sessions.py services/api/app/core/throttle.py services/api/tests/test_sessions.py
git commit -m "feat(api): Redis session store + login throttle + get_redis dep"
```

---

## Task 5: Real auth — endpoints + session-cookie swap (the multi-user cut)

This is one atomic unit: the endpoints and the `get_current_user` swap can't be split (with the stub still in place, `/auth/me` returns the dev user regardless of who logged in, so the auth tests can't pass). Ships the whole "API is now multi-user" change.

**Files:**
- Create: `services/api/app/schemas/auth.py`
- Create: `services/api/app/services/auth.py`
- Create: `services/api/app/routers/auth.py`
- Modify: `services/api/app/main.py` (include the router)
- Modify: `services/api/app/core/auth.py` (rewrite `get_current_user`)
- Modify: `services/api/tests/conftest.py` (creds seed, `redis_fake`, `client`/`auth_client` split)
- Test: `services/api/tests/test_auth_api.py`
- Regenerate: `packages/api-client/schema.gen.ts` (+ `openapi.json`)

**Interfaces:**
- Consumes: `hash_password`/`verify_password` (Task 1); `SessionStore`/`get_sessions`, `LoginThrottle`/`get_throttle` (Task 4).
- Produces: endpoints `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`; schemas `RegisterRequest`, `LoginRequest`, `UserPublic`; service `register(db, req) -> User`, `authenticate(db, req, *, throttle, ip) -> User`; `get_current_user(request, db, sessions) -> User` (401 when unauthenticated); test fixtures `client` (dev-user override, keeps existing feature tests green) and `auth_client` (real cookie flow).

- [ ] **Step 1: Write the schemas**

Create `services/api/app/schemas/auth.py`:

```python
"""Auth request/response schemas — these become the OpenAPI contract."""

import uuid
from datetime import datetime

from gulp_shared.models.user import Locale
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str | None = None
    locale: Locale = Locale.en


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    locale: Locale
    gulp_session_minutes: int
    created_at: datetime
```

Note: `EmailStr` needs `email-validator`. Add `"pydantic[email]>=2"` to `services/api/pyproject.toml` dependencies (or `"email-validator>=2"`), then `uv sync`.

- [ ] **Step 2: Write the failing test**

Create `services/api/tests/test_auth_api.py`:

```python
def test_register_sets_cookie_and_returns_user(auth_client) -> None:  # type: ignore[no-untyped-def]
    resp = auth_client.post(
        "/auth/register",
        json={"email": "New@Example.com", "password": "hunter2hunter", "display_name": "New"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"  # lowercased
    assert "password_hash" not in body
    assert "gulp_session" in resp.cookies


def test_register_rejects_duplicate_email(auth_client) -> None:  # type: ignore[no-untyped-def]
    payload = {"email": "dup@example.com", "password": "hunter2hunter"}
    assert auth_client.post("/auth/register", json=payload).status_code == 201
    resp = auth_client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_rejects_short_password(auth_client) -> None:  # type: ignore[no-untyped-def]
    resp = auth_client.post("/auth/register", json={"email": "a@b.com", "password": "short"})
    assert resp.status_code == 422


def test_login_then_me(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post("/auth/register", json={"email": "me@example.com", "password": "hunter2hunter"})
    auth_client.cookies.clear()
    login = auth_client.post("/auth/login", json={"email": "me@example.com", "password": "hunter2hunter"})
    assert login.status_code == 200
    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"


def test_login_wrong_password_is_401_generic(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post("/auth/register", json={"email": "x@example.com", "password": "hunter2hunter"})
    resp = auth_client.post("/auth/login", json={"email": "x@example.com", "password": "WRONG"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid email or password"


def test_logout_clears_session(auth_client) -> None:  # type: ignore[no-untyped-def]
    auth_client.post("/auth/register", json={"email": "out@example.com", "password": "hunter2hunter"})
    assert auth_client.get("/auth/me").status_code == 200
    auth_client.post("/auth/logout")
    auth_client.cookies.clear()  # server cleared it; drop any client copy
    assert auth_client.get("/auth/me").status_code == 401
```

The `auth_client` fixture is added in Step 7 below (same task). These tests go green after Step 6 (the `get_current_user` swap) + Step 7 (conftest).

- [ ] **Step 3: Write the service**

Create `services/api/app/services/auth.py`:

```python
"""Auth business logic (spec 2026-07-10). Routers stay thin (docs/05 D4)."""

from fastapi import HTTPException
from gulp_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.throttle import LoginThrottle
from app.schemas.auth import LoginRequest, RegisterRequest


def register(db: Session, req: RegisterRequest) -> User:
    email = req.email.lower()
    exists = db.scalar(select(User).where(User.email == email))
    if exists is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        locale=req.locale,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, req: LoginRequest, *, throttle: LoginThrottle, ip: str) -> User:
    email = req.email.lower()
    key = f"{email}:{ip}"
    if throttle.is_locked(key):
        raise HTTPException(status_code=429, detail="too many attempts, try again later")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(req.password, user.password_hash):
        throttle.record_failure(key)
        raise HTTPException(status_code=401, detail="invalid email or password")
    throttle.reset(key)
    return user
```

- [ ] **Step 4: Write the router**

Create `services/api/app/routers/auth.py`:

```python
"""Auth endpoints — thin (docs/05 D4): parse, call service, set/clear cookie."""

from fastapi import APIRouter, Depends, Request, Response
from gulp_shared.models.user import User
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.sessions import SessionStore, get_sessions
from app.core.throttle import LoginThrottle, get_throttle
from app.deps import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic
from app.services import auth as auth_service

router = APIRouter(prefix="/auth")


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(
    req: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
) -> User:
    user = auth_service.register(db, req)
    _set_cookie(response, sessions.create(user.id))
    return user


@router.post("/login", response_model=UserPublic)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
    throttle: LoginThrottle = Depends(get_throttle),
) -> User:
    ip = request.client.host if request.client else "unknown"
    user = auth_service.authenticate(db, req, throttle=throttle, ip=ip)
    _set_cookie(response, sessions.create(user.id))
    return user


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    sessions: SessionStore = Depends(get_sessions),
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        sessions.revoke(token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user
```

- [ ] **Step 5: Wire the router**

In `services/api/app/main.py`, add `auth` to the imports and include it first:

```python
from app.routers import (
    auth,
    capture,
    ...
)
...
app.include_router(auth.router, tags=["auth"])
app.include_router(capture.router, tags=["capture"])
```

- [ ] **Step 6: Rewrite `get_current_user`**

Replace `services/api/app/core/auth.py` entirely:

```python
"""Session-cookie auth (spec 2026-07-10). Resolves the session cookie to a user;
raises 401 when the cookie is absent, unknown, or expired. Every router depends
on this, so the whole API is multi-user through this one function."""

from fastapi import Depends, HTTPException, Request
from gulp_shared.models.user import User
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.core.sessions import SessionStore, get_sessions
from app.deps import get_db

_UNAUTH = HTTPException(status_code=401, detail="not authenticated")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _UNAUTH
    user_id = sessions.resolve(token)
    if user_id is None:
        raise _UNAUTH
    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTH
    return user
```

- [ ] **Step 7: Update conftest**

In `services/api/tests/conftest.py`: seed the dev user with credentials, add a `redis_fake` fixture, override `get_redis`, and split `client` (dev-user override so existing feature tests stay green) from `auth_client` (real cookie flow). Replace the `db` seed line and the `client` fixture:

```python
import fakeredis
from app.core.auth import get_current_user
from app.core.security import hash_password
from app.deps import get_db, get_enqueue, get_redis
# ... existing imports ...

@pytest.fixture
def db():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(id=DEV_USER_ID, display_name="Dev", email="dev@gulp.local", password_hash=hash_password("devpw")))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def redis_fake():  # type: ignore[no-untyped-def]
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def client(db, redis_fake):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: None)
    app.dependency_overrides[get_redis] = lambda: redis_fake
    dev = db.get(User, DEV_USER_ID)
    app.dependency_overrides[get_current_user] = lambda: dev  # existing tests are auth-agnostic
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(db, redis_fake):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: None)
    app.dependency_overrides[get_redis] = lambda: redis_fake
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 8: Run the auth endpoint tests**

Run: `cd services/api && uv run pytest tests/test_auth_api.py -v`
Expected: 6 passed (register/login/logout/me, duplicate 409, short-password 422, wrong-password 401).

- [ ] **Step 9: Regenerate the API client**

Run: `just gen-client`
Expected: `packages/api-client/schema.gen.ts` now contains `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me` paths. (The 2 pre-existing cards/job dup-identifier tsc warnings remain — ignore.)

- [ ] **Step 10: Lint + commit**

Run: `just lint`
Expected: green.

```bash
git add services/api/app/schemas/auth.py services/api/app/services/auth.py services/api/app/routers/auth.py services/api/app/main.py services/api/app/core/auth.py services/api/tests/conftest.py services/api/tests/test_auth_api.py services/api/pyproject.toml uv.lock packages/api-client/openapi.json packages/api-client/schema.gen.ts
git commit -m "feat(api): real auth — endpoints + session-cookie get_current_user (API is multi-user)"
```

---

## Task 6: Cross-user isolation tests

**Files:**
- Test: `services/api/tests/test_auth_isolation.py`

**Interfaces:** none produced; proves the swap actually isolates users and that the full existing suite still passes under the new auth.

- [ ] **Step 1: Write the isolation + 401 tests**

Create `services/api/tests/test_auth_isolation.py`:

```python
def test_unauthenticated_request_is_401(auth_client) -> None:  # type: ignore[no-untyped-def]
    assert auth_client.get("/inbox").status_code == 401


def test_users_cannot_see_each_others_snapshots(auth_client) -> None:  # type: ignore[no-untyped-def]
    # User A registers and captures a snapshot.
    auth_client.post("/auth/register", json={"email": "a@example.com", "password": "hunter2hunter"})
    cap = auth_client.post("/capture", json={"url": "https://example.com/a", "captured_via": "in_app"})
    assert cap.status_code == 200
    snap_id = cap.json()["snapshot"]["id"]

    # Switch to user B.
    auth_client.cookies.clear()
    auth_client.post("/auth/register", json={"email": "b@example.com", "password": "hunter2hunter"})

    # B cannot read A's snapshot.
    assert auth_client.get(f"/snapshots/{snap_id}").status_code == 404
    # B's inbox is empty.
    assert auth_client.get("/inbox").json()["count"] == 0
```

- [ ] **Step 2: Run the FULL api suite + lint**

Run: `cd services/api && uv run pytest -q`
Expected: all pass — existing feature tests via the `client` (dev-user) override, new tests via `auth_client`. Fix any test that asserted the old stub behavior (there should be none — feature tests are auth-agnostic through the override).
Run: `just lint`
Expected: green.

- [ ] **Step 3: Commit**

```bash
git add services/api/tests/test_auth_isolation.py
git commit -m "test(api): cross-user isolation for the session-cookie swap"
```

---

## Task 7: Ownership audit sweep

**Files:**
- Review (read): `services/api/app/services/*.py` and `services/api/app/routers/*.py`
- Test: `services/api/tests/test_ownership_audit.py`

**Interfaces:** none produced; this task confirms every read/write is owner-scoped now that real multi-user is live.

- [ ] **Step 1: Audit each service for owner scoping**

For every service function that loads a `Source`/`Card`/`GulpSession`/`ReviewEvent` (or anything reachable from them) by id, confirm it filters by the current `user.id` — the model is `_owned_snapshot` in `routers/capture.py` (raises 404 on `owner_id` mismatch). Grep for by-id loads that skip the check:

```bash
grep -rn "db.get(Source\|db.get(Card\|db.get(GulpSession\|\.query(" services/api/app/services services/api/app/routers
```

For each hit, verify an ownership guard exists (owner_id compared, or the query is `.where(... owner_id == user.id)` / joined through an owned Source). List any gaps; if a gap is found, add the guard following the `_owned_snapshot` pattern and note it in the commit.

- [ ] **Step 2: Write cross-user isolation tests for the main read paths**

Create `services/api/tests/test_ownership_audit.py` — register two users via `auth_client`, have A create data, assert B gets 404/empty on each surface (library, today, cards, pack, gulp). Example:

```python
def _register(auth_client, email):  # type: ignore[no-untyped-def]
    auth_client.cookies.clear()
    auth_client.post("/auth/register", json={"email": email, "password": "hunter2hunter"})


def test_library_is_owner_scoped(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "a@example.com")
    auth_client.post("/capture", json={"url": "https://example.com/x", "captured_via": "in_app"})
    _register(auth_client, "b@example.com")
    assert auth_client.get("/library").json()["count"] == 0


def test_cards_of_foreign_snapshot_404(auth_client) -> None:  # type: ignore[no-untyped-def]
    _register(auth_client, "a2@example.com")
    cap = auth_client.post("/capture", json={"url": "https://example.com/y", "captured_via": "in_app"})
    snap_id = cap.json()["snapshot"]["id"]
    _register(auth_client, "b2@example.com")
    assert auth_client.get(f"/snapshots/{snap_id}/cards").status_code == 404
```

- [ ] **Step 3: Run + lint + commit**

Run: `cd services/api && uv run pytest tests/test_ownership_audit.py -v`
Expected: pass. (If a real leak is found and fixed, its regression test goes here too.)
Run: `just lint`

```bash
git add services/api/tests/test_ownership_audit.py services/api/app
git commit -m "test(api): cross-user isolation audit + any owner-scoping fixes"
```

---

## Task 8: api-client — cookie transport + auth helpers

**Files:**
- Modify: `packages/api-client/src/index.ts`
- Test: (covered by web tests in later tasks; api-client has no test harness)

**Interfaces:**
- Consumes: regenerated `schema.gen.ts` (Task 5, Step 9) with `/auth/*` paths.
- Produces: `register(body)`, `login(body)`, `logout()`, `getMe()` helpers and `UserPublic` type; browser calls go to `/api` same-origin with credentials; server calls go to the absolute API URL.

- [ ] **Step 1: Make the base URL environment-aware + send credentials**

In `packages/api-client/src/index.ts`, replace the `baseUrl`/`client` block:

```ts
// Browser: same-origin "/api" (proxied by the Next rewrite) so the httpOnly
// session cookie is first-party. Server (SSR): absolute API URL — apps/web
// forwards the incoming cookie via openapi-fetch middleware (see web layout).
export const baseUrl =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    : "/api";

export const client = createClient<paths>({ baseUrl, credentials: "include" });
```

Raw-fetch helpers (`importResult`, `figureUrl`, `jobDownloadUrl`, `cardsJobDownloadUrl`, `downloadCardsJob`) already build from `baseUrl`; add `credentials: "include"` to the raw `fetch(...)` calls in `importResult` and `cardsJobReady`:

```ts
  const res = await fetch(`${baseUrl}/snapshots/${id}/import`, { method: "POST", body, credentials: "include" });
```
```ts
  const res = await fetch(cardsJobDownloadUrl(snapshotId), { method: "HEAD", credentials: "include" });
```

- [ ] **Step 2: Add the auth helpers**

Append to `packages/api-client/src/index.ts`:

```ts
export type UserPublic =
  paths["/auth/me"]["get"]["responses"]["200"]["content"]["application/json"];
export type RegisterBody =
  paths["/auth/register"]["post"]["requestBody"]["content"]["application/json"];
export type LoginBody =
  paths["/auth/login"]["post"]["requestBody"]["content"]["application/json"];

export async function register(body: RegisterBody): Promise<UserPublic> {
  const { data, error } = await client.POST("/auth/register", { body });
  if (error || !data) throw new Error("register failed");
  return data;
}

export async function login(body: LoginBody): Promise<UserPublic> {
  const { data, error } = await client.POST("/auth/login", { body });
  if (error || !data) throw new Error("login failed");
  return data;
}

export async function logout(): Promise<void> {
  await client.POST("/auth/logout", {});
}

/** Current user, or null if unauthenticated (401). */
export async function getMe(): Promise<UserPublic | null> {
  const { data, error } = await client.GET("/auth/me", { cache: "no-store" });
  if (error || !data) return null;
  return data;
}
```

- [ ] **Step 3: Type-check + commit**

Run: `cd packages/api-client && pnpm exec tsc --noEmit` (ignore the 2 pre-existing cards/job dup-identifier errors).
Run: `just lint`
Expected: green.

```bash
git add packages/api-client/src/index.ts
git commit -m "feat(api-client): cookie transport (/api same-origin) + auth helpers"
```

---

## Task 9: Next.js rewrite proxy + server-side cookie forwarding + env

**Files:**
- Modify: `apps/web/next.config.ts`
- Create: `apps/web/.env.example`
- Create: `apps/web/lib/serverApiAuth.ts`
- Modify: `apps/web/app/layout.tsx` (register server cookie-forwarding)

**Interfaces:**
- Produces: `/api/:path*` proxied to the API; server-component api-client calls carry the incoming session cookie.

- [ ] **Step 1: Add the rewrite**

Replace `apps/web/next.config.ts`:

```ts
import type { NextConfig } from "next";

const API = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["@gulp/ui"],
  async rewrites() {
    // Browser hits /api/* same-origin (first-party session cookie); Next proxies
    // to the FastAPI service. Also resolves prod cross-origin (Vercel ↔ Railway).
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};

export default nextConfig;
```

- [ ] **Step 2: Document env**

Create `apps/web/.env.example`:

```bash
# Browser talks to the API same-origin via the /api rewrite; this is the proxy target.
API_INTERNAL_URL=http://localhost:8000
# Used only if API_INTERNAL_URL is unset (kept for backwards compat).
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Forward the cookie on server-side api calls**

Create `apps/web/lib/serverApiAuth.ts`:

```ts
import "server-only";
import { cookies } from "next/headers";
import { client } from "@gulp/api-client";

// Server Components render on the Node side, where fetch has no cookie jar.
// Attach the incoming request's cookies to every api-client call so SSR data
// fetches are authenticated. This module only loads in the server bundle
// ("server-only"), so it never runs in the browser client instance.
let registered = false;

export function ensureServerApiAuth(): void {
  if (registered) return;
  registered = true;
  client.use({
    async onRequest({ request }) {
      const cookieHeader = (await cookies()).toString();
      if (cookieHeader) request.headers.set("cookie", cookieHeader);
      return request;
    },
  });
}
```

- [ ] **Step 4: Register it in the root layout**

In `apps/web/app/layout.tsx` (a Server Component), call `ensureServerApiAuth()` at the top of the default export:

```tsx
import { ensureServerApiAuth } from "@/lib/serverApiAuth";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  ensureServerApiAuth();
  return (
    // ...existing JSX unchanged...
  );
}
```

(If `layout.tsx` currently has no `import React`, add it since it now references `React.ReactNode` — or keep the existing `ReactNode` import style already used in the file.)

- [ ] **Step 5: Verify the proxy end-to-end**

Start the stack (`just dev`), then in a browser open `http://localhost:3000` — you should be redirected to `/login` once Task 12's middleware lands; for now confirm `http://localhost:3000/api/health` returns `{"status":"ok"}` (proxied).

- [ ] **Step 6: Lint + commit**

Run: `just lint`

```bash
git add apps/web/next.config.ts apps/web/.env.example apps/web/lib/serverApiAuth.ts apps/web/app/layout.tsx
git commit -m "feat(web): /api rewrite proxy + server-side cookie forwarding"
```

---

## Task 10: Auth context/provider + browser 401 handling

**Files:**
- Create: `apps/web/lib/auth.tsx` (AuthProvider + useAuth)
- Modify: `apps/web/components/shell/Shell.tsx` (wrap with AuthProvider)
- Test: `apps/web/lib/auth.test.tsx`

**Interfaces:**
- Produces: `<AuthProvider initialUser={...}>`, `useAuth() -> { user, setUser, signOut }`; a browser `onResponse` 401 handler that redirects to `/login`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/lib/auth.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { AuthProvider, useAuth } from "./auth";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, logout: vi.fn() };
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

function Probe() {
  const { user } = useAuth();
  return <span>{user ? user.email : "anon"}</span>;
}

describe("AuthProvider", () => {
  it("exposes the initial user", () => {
    const u = { id: "1", email: "me@example.com", display_name: "Me", locale: "en", gulp_session_minutes: 5, created_at: "" };
    render(<AuthProvider initialUser={u}>{<Probe />}</AuthProvider>);
    expect(screen.getByText("me@example.com")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd apps/web && pnpm exec vitest run lib/auth.test.tsx`
Expected: FAIL — `./auth` not found.

- [ ] **Step 3: Implement the provider**

Create `apps/web/lib/auth.tsx`:

```tsx
"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { client, logout as apiLogout, type UserPublic } from "@gulp/api-client";

type AuthValue = {
  user: UserPublic | null;
  setUser: (u: UserPublic | null) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({
  initialUser = null,
  children,
}: {
  initialUser?: UserPublic | null;
  children: React.ReactNode;
}) {
  const [user, setUser] = useState<UserPublic | null>(initialUser);
  const router = useRouter();

  // On a 401 from any api-client call, drop to the login screen.
  useEffect(() => {
    client.use({
      onResponse({ response }) {
        if (response.status === 401 && !location.pathname.startsWith("/login")) {
          setUser(null);
          router.replace("/login");
        }
        return response;
      },
    });
  }, [router]);

  async function signOut() {
    await apiLogout();
    setUser(null);
    router.replace("/login");
  }

  return <AuthContext.Provider value={{ user, setUser, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
```

- [ ] **Step 4: Wrap the shell**

The current user for the shell is fetched server-side. In `apps/web/components/shell/Shell.tsx` (Server Component), fetch the user and pass it as `initialUser`:

```tsx
import { getMe } from "@gulp/api-client";
import { AuthProvider } from "@/lib/auth";

export async function Shell({ children }: { children: ReactNode }) {
  const user = await getMe();
  return (
    <AuthProvider initialUser={user}>
      <CaptureProvider>
        <FullBleedGate sidebar={<Sidebar />} captureButton={<CaptureButton />}>
          {children}
        </FullBleedGate>
      </CaptureProvider>
    </AuthProvider>
  );
}
```

- [ ] **Step 5: Run test + lint, verify pass**

Run: `cd apps/web && pnpm exec vitest run lib/auth.test.tsx`
Expected: pass.
Run: `just lint`

- [ ] **Step 6: Commit**

```bash
git add apps/web/lib/auth.tsx apps/web/lib/auth.test.tsx apps/web/components/shell/Shell.tsx
git commit -m "feat(web): AuthProvider + useAuth + 401->login handling"
```

---

## Task 11: Login + register pages

**Files:**
- Create: `apps/web/app/login/page.tsx`
- Create: `apps/web/app/register/page.tsx`
- Create: `apps/web/components/auth/AuthForm.tsx`
- Create: `apps/web/components/auth/AuthForm.module.css`
- Modify: `apps/web/components/shell/FullBleedGate.tsx` (add `/login`, `/register` to `FULL_BLEED_PREFIXES`)
- Test: `apps/web/components/auth/AuthForm.test.tsx`

**Interfaces:**
- Consumes: `login`, `register`, `useAuth` (Task 8/10).
- Produces: a shared `<AuthForm mode="login" | "register" />` used by both routes.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/auth/AuthForm.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { AuthForm } from "./AuthForm";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, login: vi.fn(), register: vi.fn() };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ setUser: vi.fn() }) }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("AuthForm", () => {
  it("submits login credentials", async () => {
    (api.login as Mock).mockResolvedValue({ email: "me@example.com" });
    render(<AuthForm mode="login" />);
    await userEvent.type(screen.getByLabelText("Email"), "me@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter2hunter");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(api.login).toHaveBeenCalledWith({ email: "me@example.com", password: "hunter2hunter" });
  });

  it("surfaces an error on failure", async () => {
    (api.login as Mock).mockRejectedValue(new Error("bad"));
    render(<AuthForm mode="login" />);
    await userEvent.type(screen.getByLabelText("Email"), "me@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "hunter2hunter");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd apps/web && pnpm exec vitest run components/auth/AuthForm.test.tsx`
Expected: FAIL — `./AuthForm` not found.

- [ ] **Step 3: Implement the form**

Create `apps/web/components/auth/AuthForm.tsx`:

```tsx
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, register } from "@gulp/api-client";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import styles from "./AuthForm.module.css";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLogin = mode === "login";
  const cta = isLogin ? "Log in" : "Create account";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = isLogin
        ? await login({ email, password })
        : await register({ email, password });
      setUser(user);
      router.replace("/");
    } catch {
      setError(isLogin ? "Invalid email or password." : "Could not create the account.");
      setBusy(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={onSubmit}>
      <h1 className="t-title-l">{isLogin ? "Welcome back" : "Create your account"}</h1>
      <label className={styles.field}>
        <span className="t-label">Email</span>
        <input
          className={styles.input}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label className={styles.field}>
        <span className="t-label">Password</span>
        <input
          className={styles.input}
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <Button type="submit" variant="primary" size="lg" disabled={busy || !email || !password}>
        {busy ? "…" : cta}
      </Button>
      <p className={styles.alt}>
        {isLogin ? (
          <>No account? <Link href="/register">Create one</Link></>
        ) : (
          <>Already have an account? <Link href="/login">Log in</Link></>
        )}
      </p>
    </form>
  );
}
```

Create `apps/web/components/auth/AuthForm.module.css`:

```css
.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  width: 100%;
  max-width: 360px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-4);
  min-height: 100dvh;
  justify-content: center;
}
.field { display: flex; flex-direction: column; gap: var(--space-1); }
.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font: inherit;
}
.input:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.error { margin: 0; font-size: 13px; color: var(--danger); }
.alt { margin: 0; font-size: 14px; color: var(--text-2); }
```

- [ ] **Step 4: Create the pages**

Create `apps/web/app/login/page.tsx`:

```tsx
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return <AuthForm mode="login" />;
}
```

Create `apps/web/app/register/page.tsx`:

```tsx
import { AuthForm } from "@/components/auth/AuthForm";

export default function RegisterPage() {
  return <AuthForm mode="register" />;
}
```

- [ ] **Step 5: Make the auth routes full-bleed**

In `apps/web/components/shell/FullBleedGate.tsx`:

```tsx
const FULL_BLEED_PREFIXES = ["/gulp", "/snapshots", "/login", "/register"];
```

- [ ] **Step 6: Run test + lint, verify pass**

Run: `cd apps/web && pnpm exec vitest run components/auth/AuthForm.test.tsx`
Expected: pass.
Run: `just lint`

- [ ] **Step 7: Commit**

```bash
git add apps/web/app/login apps/web/app/register apps/web/components/auth apps/web/components/shell/FullBleedGate.tsx
git commit -m "feat(web): login + register pages"
```

---

## Task 12: Route-protection middleware + account menu (logout + current user)

**Files:**
- Create: `apps/web/middleware.ts`
- Create: `apps/web/components/shell/AccountMenu.tsx`
- Create: `apps/web/components/shell/AccountMenu.module.css`
- Modify: `apps/web/components/shell/Sidebar.tsx` (swap hardcoded account block for `<AccountMenu />`)
- Test: `apps/web/components/shell/AccountMenu.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 10), session cookie `gulp_session`.
- Produces: unauthenticated navigations redirect to `/login`; the sidebar shows the real user + a working logout.

- [ ] **Step 1: Write the middleware**

Create `apps/web/middleware.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "gulp_session"; // must match API settings.session_cookie_name
const PUBLIC_PREFIXES = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  const hasSession = request.cookies.has(SESSION_COOKIE);

  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (hasSession && isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Everything except Next internals, the API proxy, and static assets.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
```

Note: the middleware only checks cookie *presence*; the API is the real validator. A present-but-expired cookie is caught by the client 401 handler (Task 10).

- [ ] **Step 2: Write the failing AccountMenu test**

Create `apps/web/components/shell/AccountMenu.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountMenu } from "./AccountMenu";

const signOut = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { email: "me@example.com", display_name: "Me" },
    signOut,
  }),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("AccountMenu", () => {
  it("shows the user and logs out", async () => {
    render(<AccountMenu />);
    expect(screen.getByText("me@example.com")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(signOut).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run it, verify it fails**

Run: `cd apps/web && pnpm exec vitest run components/shell/AccountMenu.test.tsx`
Expected: FAIL — `./AccountMenu` not found.

- [ ] **Step 4: Implement AccountMenu**

Create `apps/web/components/shell/AccountMenu.tsx`:

```tsx
"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import styles from "./AccountMenu.module.css";

export function AccountMenu() {
  const { user, signOut } = useAuth();
  const name = user?.display_name || user?.email || "Account";
  const initial = (name[0] ?? "?").toUpperCase();

  return (
    <div className={styles.account}>
      <span className={styles.avatar} aria-hidden="true">{initial}</span>
      <div className={styles.accountText}>
        <span className={styles.accountName}>{name}</span>
        <span className={styles.accountMeta}>{user?.email}</span>
      </div>
      <button className={styles.logout} onClick={() => void signOut()}>Log out</button>
    </div>
  );
}
```

Create `apps/web/components/shell/AccountMenu.module.css` (mirror the existing Sidebar account styling; adjust to match `Sidebar.module.css`):

```css
.account { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); }
.avatar {
  display: grid; place-items: center;
  width: 28px; height: 28px; border-radius: var(--radius-pill);
  background: var(--fill); color: var(--ink); font-size: 13px; font-weight: 600;
}
.accountText { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.accountName { font-size: 13px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.accountMeta { font-size: 11px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.logout {
  border: none; background: none; cursor: pointer;
  font-size: 12px; color: var(--text-2); padding: var(--space-1);
}
.logout:hover { color: var(--ink); }
```

- [ ] **Step 5: Swap the hardcoded block in Sidebar**

In `apps/web/components/shell/Sidebar.tsx`, replace the hardcoded `<div className={styles.account}>…Mark…Free plan…</div>` block with `<AccountMenu />` (add `import { AccountMenu } from "./AccountMenu";`). Keep the Settings item as-is.

- [ ] **Step 6: Run tests + lint, verify pass**

Run: `cd apps/web && pnpm exec vitest run components/shell/AccountMenu.test.tsx`
Expected: pass.
Run: `just lint`

- [ ] **Step 7: Full manual verification**

Start the stack (`just dev`). Verify the whole flow:
1. Visit `http://localhost:3000` → redirected to `/login`.
2. Register a new account → lands on Today, sidebar shows the email.
3. Reload → still logged in (cookie persists). Capture something → it appears; log out → redirected to `/login`.
4. Log in as `dev@gulp.local` / `gulp-dev-2026` → your existing local data (snapshots, cards) is all there.
5. Register a second account → it sees none of the dev account's data.

- [ ] **Step 8: Commit**

```bash
git add apps/web/middleware.ts apps/web/components/shell/AccountMenu.tsx apps/web/components/shell/AccountMenu.module.css apps/web/components/shell/Sidebar.tsx apps/web/components/shell/AccountMenu.test.tsx
git commit -m "feat(web): route-protection middleware + account menu with logout"
```

---

## Final verification (whole feature)

- [ ] `cd services/shared && uv run pytest -q` — green
- [ ] `cd services/api && uv run pytest -q` — green
- [ ] `cd apps/web && pnpm exec vitest run` — green
- [ ] `just lint` — green
- [ ] Manual flow (Task 12 Step 7) passes end-to-end
- [ ] The dev account retains all pre-existing data; a second account is fully isolated
