# Library Width Fix & Source Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the `/library` shelf from the reader measure to the workbench width, and add per-row `media_type` + `cards_status` badges.

**Architecture:** Pure `apps/web` change. Task 1 is a one-line CSS width bump. Tasks 2–3 add a small display-only `RowBadges` component and wire it into each `LibraryList` row. All data (`media_type`, `cards_status`) already ships on the library item via `@gulp/api-client`.

**Tech Stack:** Next.js (App Router), React 19, TypeScript, CSS Modules, `@gulp/ui` tokens, Vitest + Testing Library.

## Global Constraints

- **Client-only.** No backend / schema / `@gulp/api-client` change; do NOT run `just gen-client`.
- **Types come from the contract.** Derive badge input types from `Snapshot["media_type"]` / `Snapshot["cards_status"]`; never hand-write duplicate enums.
- **Tokens from `@gulp/ui`.** Reference semantic token names (`--fill`, `--text-2`, `--blue-50`, `--blue-700`, `--muted`, `--state-risk-tint`, `--state-risk-on`, `--space-2`, `--radius-pill`); a literal fallback in `var(--x, #hex)` is allowed (matches existing code).
- **Restrained color (docs/03 §6.1):** grayscale + blue accent; red only for the `failed` error state. Badges are never color-only — a text label is always present.
- **English** in code, comments, commits. Badge labels are UI copy, kept English to match the existing Library strings ("All", "Nothing here yet").
- **Keep `just lint` green.**
- Web test command (single file): `pnpm --filter @gulp/web exec vitest run <path>`. Full web suite: `pnpm --filter @gulp/web test`.

---

### Task 1: Widen the Library shelf column (720 → 920)

**Files:**
- Modify: `apps/web/app/library/page.module.css:2`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing (CSS-only).

- [ ] **Step 1: Change the column width**

In `apps/web/app/library/page.module.css`, the `.page` rule currently reads:

```css
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px;
}
```

Change `max-width: 720px;` to `max-width: 920px;` (matches the Today page — the workbench measure; 720px is the Reader column per docs/03 §5.2). Leave the rest untouched.

- [ ] **Step 2: Verify existing web tests + lint still pass**

Run: `pnpm --filter @gulp/web test`
Expected: PASS (no test asserts on width; this confirms nothing regressed).

Run: `pnpm --filter @gulp/web lint`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/app/library/page.module.css
git commit -m "fix(web): widen Library shelf to the workbench measure (720→920)"
```

---

### Task 2: RowBadges component

**Files:**
- Create: `apps/web/components/library/RowBadges.tsx`
- Create: `apps/web/components/library/RowBadges.module.css`
- Test: `apps/web/components/library/RowBadges.test.tsx`

**Interfaces:**
- Consumes: `Snapshot` from `@gulp/api-client` (for the `media_type` / `cards_status` member types).
- Produces: `RowBadges({ mediaType, cardsStatus }: { mediaType: Snapshot["media_type"]; cardsStatus: Snapshot["cards_status"] }): JSX.Element | null` — used by Task 3.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/library/RowBadges.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RowBadges } from "./RowBadges";

afterEach(cleanup);

describe("RowBadges", () => {
  it("renders a media_type label", () => {
    render(<RowBadges mediaType="video" cardsStatus={null} />);
    expect(screen.getByText("Video")).toBeTruthy();
  });

  it("omits the media_type badge when null", () => {
    render(<RowBadges mediaType={null} cardsStatus="ready" />);
    expect(screen.queryByText("Article")).toBeNull();
    expect(screen.queryByText("PDF")).toBeNull();
  });

  it("shows cards generating and failed states", () => {
    const { rerender } = render(<RowBadges mediaType={null} cardsStatus="generating" />);
    expect(screen.getByText("Cards…")).toBeTruthy();
    rerender(<RowBadges mediaType={null} cardsStatus="failed" />);
    expect(screen.getByText("⚠ Cards")).toBeTruthy();
  });

  it("shows a subtle ready badge, and nothing when cards_status is null", () => {
    const { rerender } = render(<RowBadges mediaType={null} cardsStatus="ready" />);
    expect(screen.getByText("✓ Cards")).toBeTruthy();
    rerender(<RowBadges mediaType={null} cardsStatus={null} />);
    expect(screen.queryByText("✓ Cards")).toBeNull();
  });

  it("renders nothing when both are absent", () => {
    const { container } = render(<RowBadges mediaType={null} cardsStatus={null} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/library/RowBadges.test.tsx`
Expected: FAIL — cannot resolve `./RowBadges` (module does not exist yet).

- [ ] **Step 3: Write the component**

Create `apps/web/components/library/RowBadges.tsx`:

```tsx
import React from "react";
import type { Snapshot } from "@gulp/api-client";
import styles from "./RowBadges.module.css";

// Per-row source indicators for the Library shelf (spec 2026-07-02-library-
// width-and-source-badges): content form + cards state. Display-only; reuses
// the StateChip pill language — a text label is always present (never
// color-only).
const MEDIA_LABELS: Record<NonNullable<Snapshot["media_type"]>, string> = {
  article: "Article",
  pdf: "PDF",
  video: "Video",
  podcast: "Podcast",
  note: "Note",
  screenshot: "Screenshot",
  audio: "Audio",
  webpage: "Webpage",
};

const CARDS: Record<
  NonNullable<Snapshot["cards_status"]>,
  { label: string; variant: string }
> = {
  generating: { label: "Cards…", variant: "generating" },
  ready: { label: "✓ Cards", variant: "ready" },
  failed: { label: "⚠ Cards", variant: "failed" },
};

export function RowBadges({
  mediaType,
  cardsStatus,
}: {
  mediaType: Snapshot["media_type"];
  cardsStatus: Snapshot["cards_status"];
}) {
  const cards = cardsStatus ? CARDS[cardsStatus] : null;
  if (!mediaType && !cards) return null;
  return (
    <span className={styles.badges}>
      {mediaType && <span className={styles.media}>{MEDIA_LABELS[mediaType]}</span>}
      {cards && (
        <span className={`${styles.cards} ${styles[cards.variant]}`}>{cards.label}</span>
      )}
    </span>
  );
}
```

Create `apps/web/components/library/RowBadges.module.css`:

```css
.badges {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2, 8px);
  flex: none;
}

.media,
.cards {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-2, 8px);
  border-radius: var(--radius-pill, 999px);
  font-size: 12px;
  line-height: 16px;
  font-weight: 500;
  white-space: nowrap;
}

/* media_type — quiet grayscale metadata pill */
.media {
  background: var(--fill, #f1f5f9);
  color: var(--text-2, #64748b);
}

/* cards states — grayscale + blue accent; red only for the error */
.generating {
  background: var(--blue-50, #eff5ff);
  color: var(--blue-700, #1d4ed8);
}

.ready {
  background: transparent;
  color: var(--muted, #94a3b8);
  padding-left: 0;
  padding-right: 0;
}

.failed {
  background: var(--state-risk-tint, #fee2e2);
  color: var(--state-risk-on, #991b1b);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/library/RowBadges.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/library/RowBadges.tsx apps/web/components/library/RowBadges.module.css apps/web/components/library/RowBadges.test.tsx
git commit -m "feat(web): add RowBadges — Library media_type + cards-status indicators"
```

---

### Task 3: Render badges in each Library row

**Files:**
- Modify: `apps/web/components/library/LibraryList.tsx`
- Modify: `apps/web/components/library/LibraryList.module.css`
- Test: `apps/web/components/library/LibraryList.test.tsx`

**Interfaces:**
- Consumes: `RowBadges` from Task 2 (`./RowBadges`).
- Produces: nothing new (final integration).

- [ ] **Step 1: Write the failing integration test**

Add this test inside the `describe("LibraryList", ...)` block in `apps/web/components/library/LibraryList.test.tsx` (the existing `item()` helper defaults `media_type: "pdf"`, `cards_status: null`):

```tsx
  it("shows per-row source badges (media_type + cards status)", () => {
    render(
      <LibraryList items={[item({ media_type: "video", cards_status: "generating" })]} />,
    );
    expect(screen.getByText("Video")).toBeTruthy();
    expect(screen.getByText("Cards…")).toBeTruthy();
  });
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/library/LibraryList.test.tsx`
Expected: FAIL — "Video" / "Cards…" not found (badges not rendered yet).

- [ ] **Step 3: Render RowBadges in the row**

In `apps/web/components/library/LibraryList.tsx`, add the import near the other component imports (after the `ObjectGlyph` import):

```tsx
import { RowBadges } from "./RowBadges";
```

Then, in the row `<li>`, add `<RowBadges />` immediately after the closing `</div>` of the `.text` block so it trails the row. The `<li>` becomes:

```tsx
          <li key={item.id} className={styles.row}>
            <ObjectGlyph type="snapshot" />
            <div className={styles.text}>
              <Link href={`/snapshots/${item.id}`} className={styles.title}>
                {item.title}
              </Link>
              <span className={`t-data ${styles.meta}`}>
                {safeHost(item.origin_url)}
                {item.tags.length > 0 && ` · ${item.tags.join(" · ")}`}
              </span>
            </div>
            <RowBadges mediaType={item.media_type} cardsStatus={item.cards_status} />
          </li>
```

- [ ] **Step 4: Push badges to the right edge of the row**

In `apps/web/components/library/LibraryList.module.css`, the `.text` rule currently reads:

```css
.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
```

Add `flex: 1;` so the text block grows and the trailing badges sit at the right:

```css
.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/library/LibraryList.test.tsx`
Expected: PASS (existing 3 tests + the new badge test).

- [ ] **Step 6: Run the full web suite + lint**

Run: `pnpm --filter @gulp/web test`
Expected: PASS.

Run: `pnpm --filter @gulp/web lint`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/library/LibraryList.tsx apps/web/components/library/LibraryList.module.css apps/web/components/library/LibraryList.test.tsx
git commit -m "feat(web): show source badges on Library rows"
```

---

## Notes

- **No-op guard on `report`:** deliberately omitted — a pack is always `ready` for library items (see spec §Decisions). If a future change lets non-`ready` packs reach the Library, add a third badge here.
- **Known minor:** a `note`-type item with no URL will show both a "Note" host label (from `safeHost`) and a "Note" media badge. Acceptable for v1; not fixed here.
