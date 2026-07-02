# Sidebar Nav + Real Today Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sidebar navigate for real (route-aware highlight + working ⌘K search) and back the Today page with live data from a new `GET /today` aggregate endpoint, removing all mock data.

**Architecture:** A thin `/today` router delegates to `app/services/today.py`, which rolls up accepted-card counts, the latest ready Library items (digest), and the latest Inbox items (recents) into one `TodayOut` payload. On the web side, the sidebar splits into a server shell + client `SidebarNav` (usePathname highlight) + client `SearchCommand` (⌘K palette filtering Inbox+Library titles/tags client-side). The Today page consumes `getToday()` and drops `lib/mock.ts` entirely.

**Tech Stack:** FastAPI + SQLAlchemy (services/api, gulp_shared), Next.js App Router + CSS Modules (apps/web), openapi-fetch generated client (packages/api-client), pytest + vitest/testing-library.

## Global Constraints

- All code, comments, and commit messages in English (root CLAUDE.md rule 6).
- Web talks to the backend **only** through `@gulp/api-client` (apps/web CLAUDE.md).
- Routers stay thin; queries/logic live in `services/api/app/services` (root CLAUDE.md rule 3).
- Python tests run per-package: `cd services/api && uv run pytest` (repo-root pytest collides on the `app` namespace).
- Web tests: `pnpm --filter @gulp/web test` (vitest run).
- Do NOT run `next build` — it clobbers a running `next dev` (.next corruption). Lint + tests are the gate.
- Regenerate the TS contract with `just gen-client`; never hand-write types that duplicate it.
- Work directly on `main` (matches the current slice's commit pattern). Do not commit the untracked `abot-m05-test-cards.json` / `gulp-job-1c6447e8.zip`.

---

### Task 1: Backend `GET /today` aggregate

**Files:**
- Create: `services/api/app/schemas/today.py`
- Create: `services/api/app/services/today.py`
- Create: `services/api/app/routers/today.py`
- Modify: `services/api/app/main.py` (router registration)
- Test: `services/api/tests/test_today.py`

**Interfaces:**
- Consumes: `list_inbox(db, owner_id)`, `list_library(db, owner_id)`, `to_out(db, source)` (existing services); `Card` model (`status`, `deleted_at`, `source_id`).
- Produces: `GET /today` → `TodayOut { accepted_cards: int, card_sources: int, ready_count: int, digest: [{snapshot: SnapshotOut, accepted_cards: int}], inbox_count: int, recent: [SnapshotOut] }`; `today_summary(db: Session, owner_id: uuid.UUID) -> TodayOut`.

- [ ] **Step 1: Write the failing test**

`services/api/tests/test_today.py`:

```python
"""GET /today — the "what should I do right now?" aggregate (docs/03 §7.9)."""

from datetime import UTC, datetime

import pytest
from app.deps import get_db
from app.main import app
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from fastapi.testclient import TestClient
from gulp_shared.models.card import Card, CardOrigin, CardStatus, CardType
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _snap(db, url: str, *, status: SnapshotStatus = SnapshotStatus.ready):  # type: ignore[no-untyped-def]
    snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=url))
    snap.status = status
    db.commit()
    return snap


def _card(db, source, *, status: CardStatus = CardStatus.accepted) -> Card:  # type: ignore[no-untyped-def]
    card = Card(
        source_id=source.id,
        card_type=CardType.short_answer,
        prompt="q",
        origin=CardOrigin.pack,
        status=status,
    )
    db.add(card)
    db.commit()
    return card


def test_today_counts_accepted_cards_only(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db, "https://a.com/1")
    _card(db, snap)
    _card(db, snap)
    _card(db, snap, status=CardStatus.draft)
    _card(db, snap, status=CardStatus.rejected)
    r = client.get("/today")
    assert r.status_code == 200
    body = r.json()
    assert body["accepted_cards"] == 2
    assert body["card_sources"] == 1
    assert body["digest"][0]["accepted_cards"] == 2


def test_today_excludes_deleted_cards_and_foreign_sources(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db, "https://a.com/1")
    gone = _card(db, snap)
    gone.deleted_at = datetime.now(UTC)
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    theirs = Source(
        owner_id=other.id,
        kind=SourceKind.snapshot,
        title="theirs",
        status=SnapshotStatus.ready,
    )
    db.add(theirs)
    db.flush()
    _card(db, theirs)
    db.commit()
    r = client.get("/today")
    body = r.json()
    assert body["accepted_cards"] == 0
    assert body["card_sources"] == 0
    assert [d["snapshot"]["id"] for d in body["digest"]] == [str(snap.id)]


def test_today_digest_is_ready_only_newest_first_capped_at_3(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snaps = [_snap(db, f"https://a.com/{i}") for i in range(4)]
    _snap(db, "https://a.com/todo", status=SnapshotStatus.unprocessed)
    r = client.get("/today")
    body = r.json()
    ids = [d["snapshot"]["id"] for d in body["digest"]]
    assert ids == [str(s.id) for s in reversed(snaps)][:3]
    assert body["ready_count"] == 4


def test_today_recent_is_inbox_newest_first_capped_at_3(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    todos = [
        _snap(db, f"https://b.com/{i}", status=SnapshotStatus.unprocessed) for i in range(4)
    ]
    r = client.get("/today")
    body = r.json()
    assert body["inbox_count"] == 4
    assert [s["id"] for s in body["recent"]] == [str(s.id) for s in reversed(todos)][:3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_today.py -v`
Expected: FAIL — 404 on `/today` (router not registered) / `ModuleNotFoundError` on schema import.

- [ ] **Step 3: Write the implementation**

`services/api/app/schemas/today.py`:

```python
"""Today aggregate — the "what should I do right now?" payload (docs/03 §7.9)."""

from pydantic import BaseModel

from app.schemas.capture import SnapshotOut


class TodayDigestItem(BaseModel):
    snapshot: SnapshotOut
    accepted_cards: int


class TodayOut(BaseModel):
    accepted_cards: int
    card_sources: int
    ready_count: int
    digest: list[TodayDigestItem]
    inbox_count: int
    recent: list[SnapshotOut]
```

`services/api/app/services/today.py`:

```python
"""Today rollup — read-only aggregate of cards + library + inbox."""

import uuid

from gulp_shared.models.card import Card, CardStatus
from gulp_shared.models.source import Source
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.schemas.today import TodayDigestItem, TodayOut
from app.services.inbox import list_inbox
from app.services.library import list_library
from app.services.snapshots import to_out

DIGEST_LIMIT = 3
RECENT_LIMIT = 3


def _accepted_counts(db: Session, owner_id: uuid.UUID) -> dict[uuid.UUID, int]:
    stmt = (
        select(Card.source_id, func.count(Card.id))
        .join(Source, Card.source_id == Source.id)
        .where(
            Source.owner_id == owner_id,
            Source.deleted_at.is_(None),
            Card.deleted_at.is_(None),
            Card.status == CardStatus.accepted,
        )
        .group_by(Card.source_id)
    )
    return {sid: n for sid, n in db.execute(stmt)}


def today_summary(db: Session, owner_id: uuid.UUID) -> TodayOut:
    counts = _accepted_counts(db, owner_id)
    ready = list_library(db, owner_id)
    inbox = list_inbox(db, owner_id)
    return TodayOut(
        accepted_cards=sum(counts.values()),
        card_sources=len(counts),
        ready_count=len(ready),
        digest=[
            TodayDigestItem(snapshot=to_out(db, s), accepted_cards=counts.get(s.id, 0))
            for s in ready[:DIGEST_LIMIT]
        ],
        inbox_count=len(inbox),
        recent=[to_out(db, s) for s in inbox[:RECENT_LIMIT]],
    )
```

`services/api/app/routers/today.py`:

```python
"""Today endpoint — thin (docs/05 D4)."""

from fastapi import APIRouter, Depends
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.today import TodayOut
from app.services.today import today_summary

router = APIRouter()


@router.get("/today", response_model=TodayOut)
def get_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TodayOut:
    return today_summary(db, user.id)
```

`services/api/app/main.py` — extend the import and registration list:

```python
from app.routers import capture, cards, export, inbox, library, pack, processing, today
```

```python
app.include_router(today.router, tags=["today"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd services/api && uv run pytest tests/test_today.py -v`
Expected: 4 PASS. Then the full package: `uv run pytest` — all green.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/schemas/today.py services/api/app/services/today.py services/api/app/routers/today.py services/api/app/main.py services/api/tests/test_today.py
git commit -m "feat(api): GET /today aggregate — accepted cards, ready digest, inbox recents"
```

---

### Task 2: Regenerate api-client + `getToday()`

**Files:**
- Modify: `packages/api-client/src/index.ts`
- Generated: `packages/api-client/src/schema.gen.ts`, `packages/api-client/openapi.json` (via `just gen-client`)

**Interfaces:**
- Consumes: `/today` path in the regenerated `schema.gen.ts`.
- Produces: `export type TodayOut` and `export async function getToday(): Promise<TodayOut>` for apps/web.

- [ ] **Step 1: Regenerate the contract**

Run: `just gen-client`
Expected: `packages/api-client/src/schema.gen.ts` now contains a `"/today"` path (verify: `grep '"/today"' packages/api-client/src/schema.gen.ts`).

- [ ] **Step 2: Add the typed helper**

In `packages/api-client/src/index.ts`, after `getLibrary`:

```ts
export type TodayOut =
  paths["/today"]["get"]["responses"]["200"]["content"]["application/json"];

export async function getToday(): Promise<TodayOut> {
  const { data, error } = await client.GET("/today", { cache: "no-store" });
  if (error || !data) throw new Error("today fetch failed");
  return data;
}
```

- [ ] **Step 3: Verify it typechecks**

Run: `pnpm --filter @gulp/web exec tsc --noEmit`
Expected: no errors (web consumes the new export in Task 6; here we only confirm nothing broke).

- [ ] **Step 4: Commit**

```bash
git add packages/api-client
git commit -m "feat(api-client): regen contract with /today + getToday helper"
```

---

### Task 3: `timeAgo` utility

**Files:**
- Create: `apps/web/lib/time.ts`
- Test: `apps/web/lib/time.test.ts`

**Interfaces:**
- Produces: `timeAgo(iso: string, now?: Date): string` — coarse buckets ("just now", "12m ago", "3h ago", "yesterday", "3d ago", "Jun 10"). Treats timezone-naive ISO strings as UTC (the API serializes UTC datetimes).

- [ ] **Step 1: Write the failing test**

`apps/web/lib/time.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { timeAgo } from "./time";

const now = new Date("2026-07-02T12:00:00Z");

describe("timeAgo", () => {
  it("buckets seconds/minutes/hours/days", () => {
    expect(timeAgo("2026-07-02T11:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-07-02T11:48:00Z", now)).toBe("12m ago");
    expect(timeAgo("2026-07-02T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-07-01T09:00:00Z", now)).toBe("yesterday");
    expect(timeAgo("2026-06-29T09:00:00Z", now)).toBe("3d ago");
  });

  it("falls back to a short date beyond a week", () => {
    expect(timeAgo("2026-06-10T09:00:00Z", now)).toBe("Jun 10");
  });

  it("treats naive timestamps as UTC", () => {
    expect(timeAgo("2026-07-02T11:48:00", now)).toBe("12m ago");
  });

  it("clamps future skew to just now", () => {
    expect(timeAgo("2026-07-02T12:00:05Z", now)).toBe("just now");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run lib/time.test.ts`
Expected: FAIL — cannot resolve `./time`.

- [ ] **Step 3: Write the implementation**

`apps/web/lib/time.ts`:

```ts
// Relative "time ago" labels for capture/library rows. Coarse buckets only —
// precision below a minute reads as noise in a list.

const HAS_TZ = /Z$|[+-]\d\d:\d\d$/;

function parseUtc(iso: string): number {
  // The API serializes UTC datetimes; a naive string means UTC, not local.
  return new Date(HAS_TZ.test(iso) ? iso : `${iso}Z`).getTime();
}

export function timeAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.floor((now.getTime() - parseUtc(iso)) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  return new Date(parseUtc(iso)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run lib/time.test.ts`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/time.ts apps/web/lib/time.test.ts
git commit -m "feat(web): timeAgo relative-time utility"
```

---

### Task 4: Route-aware `SidebarNav` + sidebar refactor

**Files:**
- Create: `apps/web/components/shell/SidebarNav.tsx`
- Modify: `apps/web/components/shell/Sidebar.tsx` (drop hardcoded NAV/active, use SidebarNav, disable Settings)
- Modify: `apps/web/components/shell/Sidebar.module.css` (add `.itemDisabled`)
- Test: `apps/web/components/shell/SidebarNav.test.tsx`; update `apps/web/components/shell/Sidebar.test.tsx`

**Interfaces:**
- Consumes: `usePathname()` (next/navigation), `Link` (next/link), existing `Sidebar.module.css` classes (`nav`, `item`, `active`, `itemIcon`, `itemLabel`, `itemCount`).
- Produces: `SidebarNav({ inboxCount }: { inboxCount: number })` client component; `isActive(pathname: string, href: string): boolean` (exported for tests).

- [ ] **Step 1: Write the failing test**

`apps/web/components/shell/SidebarNav.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SidebarNav, isActive } from "./SidebarNav";

const usePathname = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ usePathname }));

afterEach(() => cleanup());

describe("isActive", () => {
  it("matches Today only on the exact root", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/inbox", "/")).toBe(false);
  });

  it("prefix-matches sections", () => {
    expect(isActive("/inbox", "/inbox")).toBe(true);
    expect(isActive("/library/x", "/library")).toBe(true);
    expect(isActive("/librarian", "/library")).toBe(false);
    expect(isActive("/snapshots/abc", "/inbox")).toBe(false);
  });
});

describe("SidebarNav", () => {
  it("marks the current route with aria-current", () => {
    usePathname.mockReturnValue("/inbox");
    render(<SidebarNav inboxCount={2} />);
    const current = screen.getByRole("link", { current: "page" });
    expect(current.textContent).toContain("Inbox");
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("marks nothing on snapshot detail pages", () => {
    usePathname.mockReturnValue("/snapshots/abc");
    render(<SidebarNav inboxCount={0} />);
    expect(screen.queryByRole("link", { current: "page" })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/shell/SidebarNav.test.tsx`
Expected: FAIL — cannot resolve `./SidebarNav`.

- [ ] **Step 3: Write the implementation**

`apps/web/components/shell/SidebarNav.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { IconToday, IconInbox, IconLibrary } from "@/components/ui/icons";
import styles from "./Sidebar.module.css";

// Single-gate nav (spec 2026-07-02): Today first, then the conveyor belt
// (Inbox = to-do) and the shelf (Library = ready). Feeds returns with S7;
// Knowledge bases are parked (tags cover grouping).
const NAV = [
  { label: "Today", href: "/", icon: IconToday },
  { label: "Inbox", href: "/inbox", icon: IconInbox },
  { label: "Library", href: "/library", icon: IconLibrary },
] as const;

// Today only on the exact root; sections match themselves and their subtree.
// /snapshots/[id] is reachable from both Inbox and Library, so nothing lights up.
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNav({ inboxCount }: { inboxCount: number }) {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Primary">
      {NAV.map(({ label, href, icon: Glyph }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={label}
            href={href}
            className={`${styles.item} ${active ? styles.active : ""}`}
            aria-current={active ? "page" : undefined}
          >
            <Glyph className={styles.itemIcon} />
            <span className={styles.itemLabel}>{label}</span>
            {label === "Inbox" && inboxCount > 0 && (
              <span className={styles.itemCount}>{inboxCount}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
```

`apps/web/components/shell/Sidebar.tsx` — full replacement:

```tsx
import { IconSearch, IconSettings } from "@/components/ui/icons";
import { getInbox } from "@gulp/api-client";
import { SidebarNav } from "./SidebarNav";
import styles from "./Sidebar.module.css";

export async function Sidebar() {
  const { count } = await getInbox();
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.mark} aria-hidden="true" />
        <span className={styles.wordmark}>Gulp</span>
      </div>

      <button type="button" className={styles.search}>
        <IconSearch className={styles.searchIcon} />
        <span>Search</span>
        <kbd className={styles.kbd}>⌘K</kbd>
      </button>

      <SidebarNav inboxCount={count} />

      <div className={styles.foot}>
        <span
          className={`${styles.item} ${styles.itemDisabled}`}
          aria-disabled="true"
          title="Coming soon"
        >
          <IconSettings className={styles.itemIcon} />
          <span className={styles.itemLabel}>Settings</span>
        </span>
        <div className={styles.account}>
          <span className={styles.avatar} aria-hidden="true">
            M
          </span>
          <div className={styles.accountText}>
            <span className={styles.accountName}>Mark</span>
            <span className={styles.accountMeta}>Free plan</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
```

(The static search button is swapped for `SearchCommand` in Task 5.)

Append to `apps/web/components/shell/Sidebar.module.css`:

```css
/* Settings is a placeholder until there is anything to set. */
.itemDisabled {
  opacity: 0.55;
  cursor: default;
}
.itemDisabled:hover {
  background: none;
  color: var(--text-2);
}
```

Update `apps/web/components/shell/Sidebar.test.tsx` — add the next/navigation mock below the api-client mock (the nav is now a client child that calls `usePathname`):

```tsx
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/shell`
Expected: SidebarNav tests PASS; existing Sidebar test still PASS (nav order + hrefs unchanged).

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/shell
git commit -m "feat(web): route-aware sidebar nav — highlight follows the pathname"
```

---

### Task 5: ⌘K search palette

**Files:**
- Create: `apps/web/lib/search.ts`
- Create: `apps/web/components/shell/SearchCommand.tsx`
- Create: `apps/web/components/shell/SearchCommand.module.css`
- Modify: `apps/web/components/shell/Sidebar.tsx` (swap static button for `<SearchCommand />`)
- Test: `apps/web/lib/search.test.ts`, `apps/web/components/shell/SearchCommand.test.tsx`

**Interfaces:**
- Consumes: `getInbox()`, `getLibrary()` from `@gulp/api-client` (browser-side; CORS already allows the web origin), `useRouter()` from next/navigation, `Sidebar.module.css` classes `search`/`searchIcon`/`kbd`.
- Produces: `SearchEntry { id, title, tags, href, kind: "page" | "snapshot" }`, `filterEntries(entries, query, limit = 8): SearchEntry[]`, `SearchCommand()` client component.

- [ ] **Step 1: Write the failing filter test**

`apps/web/lib/search.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { filterEntries, type SearchEntry } from "./search";

const entries: SearchEntry[] = [
  { id: "1", title: "The Bitter Lesson", tags: ["ai"], href: "/snapshots/1", kind: "snapshot" },
  { id: "2", title: "Spaced repetition", tags: ["memory"], href: "/snapshots/2", kind: "snapshot" },
  { id: "3", title: "Inbox", tags: [], href: "/inbox", kind: "page" },
];

describe("filterEntries", () => {
  it("returns the head of the list for an empty query", () => {
    expect(filterEntries(entries, "  ")).toEqual(entries);
  });

  it("matches titles case-insensitively", () => {
    expect(filterEntries(entries, "BITTER").map((e) => e.id)).toEqual(["1"]);
  });

  it("matches tags", () => {
    expect(filterEntries(entries, "memory").map((e) => e.id)).toEqual(["2"]);
  });

  it("caps results at the limit", () => {
    const many = Array.from({ length: 12 }, (_, i) => ({
      id: String(i),
      title: `note ${i}`,
      tags: [],
      href: `/snapshots/${i}`,
      kind: "snapshot" as const,
    }));
    expect(filterEntries(many, "note")).toHaveLength(8);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run lib/search.test.ts`
Expected: FAIL — cannot resolve `./search`.

- [ ] **Step 3: Implement the filter**

`apps/web/lib/search.ts`:

```ts
// ⌘K palette entries + matching. Client-side substring match over titles and
// tags — the corpus is one user's snapshots, so no server round-trip needed.

export interface SearchEntry {
  id: string;
  title: string;
  tags: string[];
  href: string;
  kind: "page" | "snapshot";
}

export function filterEntries(
  entries: SearchEntry[],
  query: string,
  limit = 8,
): SearchEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return entries.slice(0, limit);
  return entries
    .filter(
      (e) =>
        e.title.toLowerCase().includes(q) ||
        e.tags.some((t) => t.toLowerCase().includes(q)),
    )
    .slice(0, limit);
}
```

Run: `pnpm --filter @gulp/web exec vitest run lib/search.test.ts` — 4 PASS.

- [ ] **Step 4: Write the failing component test**

`apps/web/components/shell/SearchCommand.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SearchCommand } from "./SearchCommand";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@gulp/api-client", () => ({
  getInbox: vi.fn().mockResolvedValue({ items: [], count: 0 }),
  getLibrary: vi.fn().mockResolvedValue({
    items: [{ id: "s1", title: "The Bitter Lesson", tags: ["ai"] }],
    count: 1,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SearchCommand", () => {
  it("opens on click, filters, and navigates on Enter", async () => {
    render(<SearchCommand />);
    fireEvent.click(screen.getByRole("button", { name: /search/i }));
    const input = await screen.findByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: "bitter" } });
    await screen.findByText("The Bitter Lesson");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/snapshots/s1");
  });

  it("opens with ⌘K and closes with Escape", () => {
    render(<SearchCommand />);
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Search" })).toBeNull();
  });
});
```

Run: `pnpm --filter @gulp/web exec vitest run components/shell/SearchCommand.test.tsx`
Expected: FAIL — cannot resolve `./SearchCommand`.

- [ ] **Step 5: Implement the palette**

`apps/web/components/shell/SearchCommand.tsx`:

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getInbox, getLibrary } from "@gulp/api-client";
import { filterEntries, type SearchEntry } from "@/lib/search";
import { IconSearch } from "@/components/ui/icons";
import sidebar from "./Sidebar.module.css";
import styles from "./SearchCommand.module.css";

const PAGES: SearchEntry[] = [
  { id: "page-today", title: "Today", tags: [], href: "/", kind: "page" },
  { id: "page-inbox", title: "Inbox", tags: [], href: "/inbox", kind: "page" },
  { id: "page-library", title: "Library", tags: [], href: "/library", kind: "page" },
];

// ⌘K command palette (docs/03 §5.2). Corpus = static pages + every snapshot
// in Inbox and Library, fetched fresh on open.
export function SearchCommand() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [snapshots, setSnapshots] = useState<SearchEntry[]>([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    let cancelled = false;
    Promise.all([getLibrary(), getInbox()])
      .then(([library, inbox]) => {
        if (cancelled) return;
        setSnapshots(
          [...library.items, ...inbox.items].map((s) => ({
            id: s.id,
            title: s.title,
            tags: s.tags,
            href: `/snapshots/${s.id}`,
            kind: "snapshot" as const,
          })),
        );
      })
      .catch(() => setSnapshots([]));
    return () => {
      cancelled = true;
    };
  }, [open]);

  const results = useMemo(
    () => filterEntries([...PAGES, ...snapshots], query),
    [snapshots, query],
  );

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const onInputKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      go(results[active].href);
    }
  };

  return (
    <>
      <button type="button" className={sidebar.search} onClick={() => setOpen(true)}>
        <IconSearch className={sidebar.searchIcon} />
        <span>Search</span>
        <kbd className={sidebar.kbd}>⌘K</kbd>
      </button>

      {open && (
        <div className={styles.overlay} onClick={() => setOpen(false)}>
          <div
            className={styles.panel}
            role="dialog"
            aria-label="Search"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.inputRow}>
              <IconSearch className={styles.inputIcon} />
              <input
                autoFocus
                className={styles.input}
                placeholder="Search snapshots, tags, pages…"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={onInputKey}
              />
              <kbd className={sidebar.kbd}>esc</kbd>
            </div>
            <ul className={styles.results} role="listbox" aria-label="Results">
              {results.map((r, i) => (
                <li key={r.id}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === active}
                    className={`${styles.result} ${i === active ? styles.resultActive : ""}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(r.href)}
                  >
                    <span className={styles.resultTitle}>{r.title}</span>
                    <span className={styles.resultKind}>
                      {r.kind === "page" ? "Page" : "Snapshot"}
                    </span>
                  </button>
                </li>
              ))}
              {results.length === 0 && <li className={styles.emptyRow}>No matches</li>}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
```

`apps/web/components/shell/SearchCommand.module.css`:

```css
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 15vh;
}
.panel {
  width: min(560px, calc(100vw - 32px));
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 16px 48px rgba(15, 23, 42, 0.18);
  overflow: hidden;
}

.inputRow {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
}
.inputIcon {
  width: 16px;
  height: 16px;
  color: var(--muted);
  flex: none;
}
.input {
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: 14px;
  color: var(--text-1);
}

.results {
  max-height: 320px;
  overflow-y: auto;
  padding: var(--space-2);
  margin: 0;
  list-style: none;
}
.result {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 0;
  background: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-1);
  text-align: left;
  cursor: pointer;
}
.resultActive {
  background: var(--fill);
}
.resultTitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.resultKind {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  flex: none;
}
.emptyRow {
  padding: var(--space-3);
  font-size: 13px;
  color: var(--text-2);
}
```

In `apps/web/components/shell/Sidebar.tsx`: remove the static search `<button>` and the now-unused `IconSearch` import; render `<SearchCommand />` in its place:

```tsx
import { IconSettings } from "@/components/ui/icons";
import { getInbox } from "@gulp/api-client";
import { SidebarNav } from "./SidebarNav";
import { SearchCommand } from "./SearchCommand";
```

```tsx
      <SearchCommand />

      <SidebarNav inboxCount={count} />
```

Update the next/navigation mock in `apps/web/components/shell/Sidebar.test.tsx` — `SearchCommand` calls `useRouter()` during render, so the mock must provide it:

```tsx
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn() }),
}));
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/shell lib/search.test.ts`
Expected: all PASS (Sidebar.test.tsx still green — the search button markup is unchanged inside SearchCommand).

- [ ] **Step 7: Commit**

```bash
git add apps/web/lib/search.ts apps/web/lib/search.test.ts apps/web/components/shell
git commit -m "feat(web): ⌘K search palette over inbox + library"
```

---

### Task 6: Today page on real data — delete `lib/mock.ts`

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/components/today/StartGulpCard.tsx` + `StartGulpCard.module.css`
- Modify: `apps/web/components/today/DigestCard.tsx`
- Modify: `apps/web/components/today/CapturePeek.tsx` (own `RecentItem` type)
- Modify: `apps/web/components/ui/ObjectGlyph.tsx` (own `ObjectType`), `apps/web/components/ui/StateChip.tsx` (own `MasteryState`)
- Modify: `apps/web/components/ui/Button.module.css` (add `:disabled`)
- Modify: `apps/web/app/page.module.css` (add `.empty`)
- Delete: `apps/web/lib/mock.ts`
- Test: `apps/web/app/page.test.tsx`

**Interfaces:**
- Consumes: `getToday(): Promise<TodayOut>` (Task 2), `timeAgo` (Task 3), existing `ObjectGlyph`/`CapturePeek` markup and CSS.
- Produces: `TodayPage` server component on live data; `ObjectType` exported from `ObjectGlyph`, `MasteryState` exported from `StateChip`, `RecentItem` exported from `CapturePeek`.

- [ ] **Step 1: Write the failing test**

`apps/web/app/page.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import * as api from "@gulp/api-client";
import TodayPage from "./page";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getToday: vi.fn() };
});

const snap = (over: Record<string, unknown>) => ({
  id: "s1",
  kind: "snapshot",
  title: "The Bitter Lesson",
  note: null,
  status: "ready",
  media_type: null,
  origin_url: "https://a.com/x",
  content_body: null,
  captured_via: "in_app",
  cards_status: null,
  tags: [],
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  ...over,
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TodayPage", () => {
  it("renders live counts, digest, and recents", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 4,
      card_sources: 2,
      ready_count: 2,
      digest: [{ snapshot: snap({}), accepted_cards: 4 }],
      inbox_count: 1,
      recent: [snap({ id: "s2", status: "processing", title: "Import AI" })],
    });
    render(await TodayPage());
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText("The Bitter Lesson")).toBeTruthy();
    expect(screen.getByText("Import AI")).toBeTruthy();
  });

  it("shows empty states", async () => {
    (api.getToday as ReturnType<typeof vi.fn>).mockResolvedValue({
      accepted_cards: 0,
      card_sources: 0,
      ready_count: 0,
      digest: [],
      inbox_count: 0,
      recent: [],
    });
    render(await TodayPage());
    expect(screen.getByText(/Nothing ready yet/)).toBeTruthy();
    expect(screen.getByText(/Inbox is clear/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run app/page.test.tsx`
Expected: FAIL — `getToday` not mocked into old page / old page imports `@/lib/mock` shape.

- [ ] **Step 3: Move the view types off mock.ts**

`apps/web/components/ui/ObjectGlyph.tsx` — replace the mock import with a local export:

```tsx
import React from "react";
import { IconSnapshot, IconConversation, IconSubscription } from "./icons";
import styles from "./ObjectGlyph.module.css";

// Core object taxonomy (docs/03 §2.4) — conversation/subscription arrive in
// later slices; the glyph set is already stable.
export type ObjectType = "snapshot" | "conversation" | "subscription";
```

`apps/web/components/ui/StateChip.tsx` — same move:

```tsx
import styles from "./StateChip.module.css";

// Mastery states (docs/03 §7.2) — real scheduling lands with S5.
export type MasteryState = "new" | "learning" | "known" | "due" | "at-risk";
```

`apps/web/components/today/CapturePeek.tsx` — own the row view-model:

```tsx
import { ObjectGlyph, type ObjectType } from "@/components/ui/ObjectGlyph";
import { IconAlert } from "@/components/ui/icons";
import styles from "./CapturePeek.module.css";

export interface RecentItem {
  id: string;
  type: ObjectType;
  title: string;
  source: string;
  time: string;
  status: "ready" | "processing" | "attention";
}
```

(Rest of CapturePeek unchanged.)

- [ ] **Step 4: Rewrite StartGulpCard and DigestCard**

`apps/web/components/today/StartGulpCard.tsx` — full replacement:

```tsx
import { Button } from "@/components/ui/Button";
import { IconArrowRight } from "@/components/ui/icons";
import styles from "./StartGulpCard.module.css";

// The "what to do now" hero (docs/03 §7.9). Counts are live (accepted cards
// across the library); the practice loop itself ships with scheduling (S5),
// so the CTA stays disabled until then.
export function StartGulpCard({
  acceptedCards,
  cardSources,
}: {
  acceptedCards: number;
  cardSources: number;
}) {
  return (
    <section className={styles.hero}>
      <div className={styles.body}>
        <p className="t-label">Ready to practice</p>
        <p className={styles.count}>
          <span className={styles.num}>{acceptedCards}</span>
          <span className={styles.unit}>cards ready</span>
        </p>
        <p className={styles.meta}>
          {acceptedCards > 0 ? (
            <>
              across <span className="t-data">{cardSources}</span>{" "}
              {cardSources === 1 ? "source" : "sources"} in your library
            </>
          ) : (
            <>Accept cards on a ready snapshot to build your deck.</>
          )}
        </p>
      </div>

      <div className={styles.action}>
        <Button variant="primary" size="lg" disabled iconRight={<IconArrowRight />}>
          Start Gulp
        </Button>
        <p className={styles.actionHint}>Practice mode is coming soon</p>
      </div>
    </section>
  );
}
```

`StartGulpCard.module.css` — delete the `.resume` / `.resumeChevron` rules (and their comment); replace `.action` and add `.actionHint`:

```css
.action {
  align-self: center;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-2);
}
.actionHint {
  font-size: 12px;
  color: var(--muted);
}
```

`apps/web/components/today/DigestCard.tsx` — full replacement (card links to its snapshot):

```tsx
import Link from "next/link";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { timeAgo } from "@/lib/time";
import type { TodayOut } from "@gulp/api-client";
import styles from "./DigestCard.module.css";

type TodayDigestItem = TodayOut["digest"][number];

// Object card (docs/03 §7.1): type glyph · title · optional note · mono meta.
// The mastery chip and "why it connects" line return when scheduling lands (S5).
export function DigestCard({ item }: { item: TodayDigestItem }) {
  const { snapshot } = item;
  const source = snapshot.origin_url ? new URL(snapshot.origin_url).host : "Note";
  return (
    <Link href={`/snapshots/${snapshot.id}`} className={styles.card}>
      <div className={styles.top}>
        <ObjectGlyph type="snapshot" />
      </div>

      <h3 className={`t-title-s ${styles.title}`}>{snapshot.title}</h3>
      {snapshot.note && (
        <p className={`t-body-s ${styles.summary}`}>{snapshot.note}</p>
      )}

      <div className={styles.meta}>
        <span className="t-data">{source}</span>
        <span className={styles.dot}>·</span>
        <span className="t-data">{timeAgo(snapshot.created_at)}</span>
        <span className={styles.cards}>
          <span className="t-data">+{item.accepted_cards}</span> cards
        </span>
      </div>
    </Link>
  );
}
```

`apps/web/components/ui/Button.module.css` — append:

```css
.btn:disabled {
  opacity: 0.55;
  cursor: default;
  pointer-events: none;
}
```

- [ ] **Step 5: Rewrite the page + delete mock**

`apps/web/app/page.tsx` — full replacement:

```tsx
export const dynamic = "force-dynamic";

import Link from "next/link";
import { StartGulpCard } from "@/components/today/StartGulpCard";
import { DigestCard } from "@/components/today/DigestCard";
import { CapturePeek, type RecentItem } from "@/components/today/CapturePeek";
import { getToday } from "@gulp/api-client";
import { timeAgo } from "@/lib/time";
import styles from "./page.module.css";

// Today — the web "what should I do right now?" landing (docs/03 §7.9).
export default async function TodayPage() {
  const today = await getToday();
  const date = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  const recent: RecentItem[] = today.recent.map((s) => ({
    id: s.id,
    type: "snapshot",
    title: s.title,
    source: s.origin_url ? new URL(s.origin_url).host : "Note",
    time: timeAgo(s.created_at),
    status:
      s.status === "needs_attention"
        ? "attention"
        : s.status === "ready"
          ? "ready"
          : "processing",
  }));

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className="t-title-l">Today</h1>
          <p className={styles.greeting}>
            Here&apos;s what&apos;s worth your 5 minutes.
          </p>
        </div>
        <span className={`t-data ${styles.dateChip}`}>{date}</span>
      </header>

      <StartGulpCard
        acceptedCards={today.accepted_cards}
        cardSources={today.card_sources}
      />

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently ready</p>
          <Link href="/library" className={styles.seeAll}>
            See all
          </Link>
        </div>
        {today.digest.length > 0 ? (
          <div className={styles.digestGrid}>
            {today.digest.map((item) => (
              <DigestCard key={item.snapshot.id} item={item} />
            ))}
          </div>
        ) : (
          <p className={styles.empty}>
            Nothing ready yet — process a capture from your Inbox.
          </p>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <p className="t-label">Recently captured</p>
          <Link href="/inbox" className={styles.seeAll}>
            Open Inbox
          </Link>
        </div>
        {recent.length > 0 ? (
          <CapturePeek items={recent} />
        ) : (
          <p className={styles.empty}>Inbox is clear.</p>
        )}
      </section>
    </div>
  );
}
```

`apps/web/app/page.module.css` — append:

```css
.empty {
  padding: var(--space-4);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  color: var(--text-2);
  font-size: 13px;
}
```

Delete the mock:

```bash
rm apps/web/lib/mock.ts
```

Then confirm nothing still imports it: `grep -rn "lib/mock" apps/web --include="*.ts*" | grep -v node_modules` → no output.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web test`
Expected: all web tests PASS (page, shell, lib, existing suites).

- [ ] **Step 7: Commit**

```bash
git add -A apps/web
git commit -m "feat(web): Today page on live /today data — mock payload deleted"
```

---

### Task 7: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Backend suite**

Run: `cd services/api && uv run pytest`
Expected: all PASS.

- [ ] **Step 2: Web suite**

Run: `pnpm --filter @gulp/web test`
Expected: all PASS.

- [ ] **Step 3: Lint gates**

Run: `just lint`
Expected: green across eslint + ruff + mypy (the repo keeps this green — fix anything it flags before committing).

- [ ] **Step 4: Commit any lint fixups**

```bash
git status --short   # only commit files this plan touched
git add <fixed files> && git commit -m "chore: lint fixups for sidebar/today slice"
```

(Skip if nothing changed.)
