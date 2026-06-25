# S2 Web Slice — Plan B: Reader + Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the web snapshot-detail page that renders the re-authored report + facets (report-first layout), with `processing`/`ready`/`needs_attention` states, light polling, and a ▶ Start control (detail + Inbox row) so captures get processed and read.

**Architecture:** Pure helpers in `lib/pack.ts` (facet grouping, poll predicate) are unit-tested; presentational components (`PackReport`, `FacetRail`) are tested via `renderToStaticMarkup` (no RTL); client islands (`StartButton`, `ProcessingPoller`, `ReaderToggle`) hold the interactive bits; the RSC page `app/snapshots/[id]/page.tsx` fetches `getSnapshot`/`getPack` and branches on status. Consumes Plan A's `@gulp/api-client` helpers.

**Tech Stack:** Next.js 15 App Router (RSC + client islands), React 19, TypeScript, CSS modules + `@gulp/ui` tokens, vitest + jsdom (existing), `@gulp/api-client`.

## Global Constraints

- **Talk to the backend only through `@gulp/api-client`** (`apps/web/CLAUDE.md`): use `getSnapshot`, `getPack` (null on 404), `startProcessing` (Plan A). Never hand-write fetch types.
- **Visual primitives from `@gulp/ui`** (`Button`) and tokens (CSS vars `--text-1`/`--text-muted`/`--accent`/`--border`/`--radius-*`, text classes `t-title-l`/`t-data`); don't redefine tokens. Per-component CSS modules.
- **Report-first layout** (design spec, your pick): the report is the main column; facets in a side rail; `Pack ⇄ Original` toggle.
- **English** copy/comments/commits. (Product UI copy may be English here — this is a learning surface, and the slice ships English-only.)
- **No new test deps:** test pure logic with vitest and presentational components with `react-dom/server`'s `renderToStaticMarkup` (already a dep). Interactive client islands are covered by their extracted logic + the build; the visual is eyeballed (matches the S1 web convention).
- **Gate:** `pnpm --filter @gulp/web test` (vitest) GREEN and `pnpm --filter @gulp/web build` (Next type-checks + builds) GREEN. (Repo-wide eslint not installed = accepted baseline.)
- **TDD where there's logic; commit per task.**

---

## File Structure

- `apps/web/lib/pack.ts` *(new)* — `groupFacets(facets)`, `isProcessing(status)`, `FACET_ORDER`/labels. Pure.
- `apps/web/lib/pack.test.ts` *(new)* — unit tests for the helpers.
- `apps/web/components/snapshot/PackReport.tsx` + `.module.css` *(new)* — renders `sections → blocks`.
- `apps/web/components/snapshot/FacetRail.tsx` + `.module.css` *(new)* — grouped facets.
- `apps/web/components/snapshot/PackReport.test.tsx` *(new)* — `renderToStaticMarkup` tests for both presentational components.
- `apps/web/components/snapshot/ReaderToggle.tsx` + `.module.css` *(new, client)* — Pack ⇄ Original.
- `apps/web/components/snapshot/StartButton.tsx` *(new, client)* — `startProcessing` + `router.refresh()`.
- `apps/web/components/snapshot/ProcessingPoller.tsx` *(new, client)* — poll until not `processing`.
- `apps/web/components/snapshot/SnapshotStatusView.module.css` *(new)* — skeleton + banner styles.
- `apps/web/app/snapshots/[id]/page.tsx` *(new)* — the RSC detail page (status branching + wiring).
- `apps/web/components/inbox/InboxRow.tsx` *(modify)* — link to `/snapshots/[id]` + a Start affordance.

Task order: helpers → presentational components → client islands → page + inbox wiring.

---

### Task 1: `lib/pack.ts` helpers

**Files:**
- Create: `apps/web/lib/pack.ts`, `apps/web/lib/pack.test.ts`

**Interfaces:**
- Produces: `type FacetGroup = { type: ElementType; label: string; items: Facet[] }`; `groupFacets(facets: Facet[]): FacetGroup[]` (ordered by `FACET_ORDER`, only non-empty groups); `isProcessing(status: Snapshot["status"]): boolean`. `Facet`/`ElementType` derived from `PackOut`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/lib/pack.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { groupFacets, isProcessing } from "./pack";
import type { PackOut } from "@gulp/api-client";

type Facet = PackOut["facets"][number];

const facets: Facet[] = [
  { element_type: "claim", text: "c1" },
  { element_type: "key_term", text: "t1" },
  { element_type: "claim", text: "c2" },
];

describe("groupFacets", () => {
  it("orders groups and keeps only non-empty ones", () => {
    const groups = groupFacets(facets);
    expect(groups.map((g) => g.type)).toEqual(["key_term", "claim"]); // FACET_ORDER, no empties
    expect(groups[0].label).toBe("Key terms");
    expect(groups[1].items.map((f) => f.text)).toEqual(["c1", "c2"]);
  });

  it("returns [] for no facets", () => {
    expect(groupFacets([])).toEqual([]);
  });
});

describe("isProcessing", () => {
  it("is true only for processing", () => {
    expect(isProcessing("processing")).toBe(true);
    expect(isProcessing("ready")).toBe(false);
    expect(isProcessing("needs_attention")).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run lib/pack.test.ts`
Expected: FAIL — cannot find `./pack`.

- [ ] **Step 3: Write the helpers**

Create `apps/web/lib/pack.ts`:

```typescript
import type { PackOut, Snapshot } from "@gulp/api-client";

export type Facet = PackOut["facets"][number];
export type ElementType = Facet["element_type"];

const FACET_ORDER: { type: ElementType; label: string }[] = [
  { type: "key_term", label: "Key terms" },
  { type: "person_org", label: "People & orgs" },
  { type: "claim", label: "Claims" },
  { type: "counter_view", label: "Counter-views" },
  { type: "connection", label: "Connections" },
];

export interface FacetGroup {
  type: ElementType;
  label: string;
  items: Facet[];
}

export function groupFacets(facets: Facet[]): FacetGroup[] {
  return FACET_ORDER.map(({ type, label }) => ({
    type,
    label,
    items: facets.filter((f) => f.element_type === type),
  })).filter((g) => g.items.length > 0);
}

// The poller keeps going while the snapshot is still being processed.
export function isProcessing(status: Snapshot["status"]): boolean {
  return status === "processing";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run lib/pack.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/pack.ts apps/web/lib/pack.test.ts
git commit -m "feat(web): pack facet-grouping + poll helpers"
```

---

### Task 2: `PackReport` + `FacetRail` presentational components

**Files:**
- Create: `apps/web/components/snapshot/PackReport.tsx`, `apps/web/components/snapshot/PackReport.module.css`, `apps/web/components/snapshot/FacetRail.tsx`, `apps/web/components/snapshot/FacetRail.module.css`, `apps/web/components/snapshot/PackReport.test.tsx`

**Interfaces:**
- Consumes: `PackOut` (`@gulp/api-client`), `groupFacets` (Task 1).
- Produces: `PackReport({ pack }: { pack: PackOut })` — renders `summary`, optional `background`, then each section (`heading` + blocks; block `type` styles prose/callout/quote). `FacetRail({ facets }: { facets: PackOut["facets"] })` — `groupFacets` → labeled groups; `key_term`/`person_org` as chips, others as short lines. Both presentational (no hooks), so server- or client-renderable.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/PackReport.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";
import { FacetRail } from "./FacetRail";

const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  summary: "A short summary.",
  background: "Some background.",
  confidence: 0.8,
  sections: [
    { heading: "Overview", blocks: [{ type: "prose", content: "First paragraph.", anchor_id: "s0b0" }] },
    { heading: "Detail", blocks: [{ type: "quote", content: "A quote.", anchor_id: "s1b0" }] },
  ],
  facets: [
    { element_type: "key_term", text: "attention" },
    { element_type: "claim", text: "Claim one." },
  ],
};

describe("PackReport", () => {
  it("renders summary, headings, and block content", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("A short summary.");
    expect(html).toContain("Overview");
    expect(html).toContain("First paragraph.");
    expect(html).toContain("A quote.");
  });
});

describe("FacetRail", () => {
  it("renders grouped facet labels and items", () => {
    const html = renderToStaticMarkup(<FacetRail facets={pack.facets} />);
    expect(html).toContain("Key terms");
    expect(html).toContain("attention");
    expect(html).toContain("Claims");
    expect(html).toContain("Claim one.");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: FAIL — cannot find `./PackReport`.

- [ ] **Step 3: Write `PackReport`**

Create `apps/web/components/snapshot/PackReport.module.css`:

```css
.report { max-width: 680px; }
.summary { font-size: 16px; line-height: 24px; color: var(--text-1); margin-bottom: 20px; }
.background { color: var(--text-muted, #777); margin-bottom: 24px; }
.section { margin-bottom: 24px; }
.heading { font-weight: 600; font-size: 18px; line-height: 24px; margin-bottom: 10px; }
.prose { line-height: 22px; margin-bottom: 10px; }
.quote { border-left: 2px solid var(--border, #ddd); padding-left: 12px; color: var(--text-muted, #555); margin-bottom: 10px; }
.callout { background: var(--surface-2, #f6f6f6); border-radius: var(--radius-sm, 6px); padding: 10px 12px; margin-bottom: 10px; }
```

Create `apps/web/components/snapshot/PackReport.tsx`:

```tsx
import type { PackOut } from "@gulp/api-client";
import styles from "./PackReport.module.css";

const BLOCK_CLASS: Record<string, string> = {
  prose: styles.prose,
  quote: styles.quote,
  callout: styles.callout,
  figure: styles.callout, // figures deferred — render their text content for now
};

export function PackReport({ pack }: { pack: PackOut }) {
  return (
    <article className={styles.report}>
      <p className={styles.summary}>{pack.summary}</p>
      {pack.background && <p className={styles.background}>{pack.background}</p>}
      {pack.sections.map((section, i) => (
        <section key={i} className={styles.section}>
          {section.heading && <h2 className={styles.heading}>{section.heading}</h2>}
          {section.blocks.map((block) => (
            <p key={block.anchor_id} className={BLOCK_CLASS[block.type] ?? styles.prose}>
              {block.content}
            </p>
          ))}
        </section>
      ))}
    </article>
  );
}
```

- [ ] **Step 4: Write `FacetRail`**

Create `apps/web/components/snapshot/FacetRail.module.css`:

```css
.rail { display: flex; flex-direction: column; gap: 16px; }
.group { }
.label { text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; color: var(--text-muted, #999); margin-bottom: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { border: 1px solid var(--border, #ddd); border-radius: 999px; padding: 2px 10px; font-size: 13px; }
.line { font-size: 13px; line-height: 18px; color: var(--text-1); margin-bottom: 6px; }
```

Create `apps/web/components/snapshot/FacetRail.tsx`:

```tsx
import type { PackOut } from "@gulp/api-client";
import { groupFacets } from "@/lib/pack";
import styles from "./FacetRail.module.css";

const CHIP_TYPES = new Set(["key_term", "person_org"]);

export function FacetRail({ facets }: { facets: PackOut["facets"] }) {
  const groups = groupFacets(facets);
  if (groups.length === 0) return null;
  return (
    <aside className={styles.rail}>
      {groups.map((group) => (
        <div key={group.type} className={styles.group}>
          <div className={styles.label}>{group.label}</div>
          {CHIP_TYPES.has(group.type) ? (
            <div className={styles.chips}>
              {group.items.map((f, i) => (
                <span key={i} className={styles.chip}>{f.text}</span>
              ))}
            </div>
          ) : (
            group.items.map((f, i) => (
              <p key={i} className={styles.line}>{f.text}</p>
            ))
          )}
        </div>
      ))}
    </aside>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/snapshot/PackReport.tsx apps/web/components/snapshot/PackReport.module.css apps/web/components/snapshot/FacetRail.tsx apps/web/components/snapshot/FacetRail.module.css apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): PackReport + FacetRail presentational components"
```

---

### Task 3: Client islands — `StartButton`, `ProcessingPoller`, `ReaderToggle`

**Files:**
- Create: `apps/web/components/snapshot/StartButton.tsx`, `apps/web/components/snapshot/ProcessingPoller.tsx`, `apps/web/components/snapshot/ReaderToggle.tsx`, `apps/web/components/snapshot/ReaderToggle.module.css`

**Interfaces:**
- Consumes: `startProcessing`, `getSnapshot` (`@gulp/api-client`); `isProcessing`, `PackReport`, `FacetRail` (Tasks 1–2); `next/navigation` `useRouter`.
- Produces: `StartButton({ id, label }: { id: string; label?: string })`; `ProcessingPoller({ id }: { id: string })`; `ReaderToggle({ pack, original }: { pack: PackOut; original: string | null })`. All `"use client"`.

- [ ] **Step 1: Write `StartButton`**

Create `apps/web/components/snapshot/StartButton.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { startProcessing } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

export function StartButton({ id, label = "▶ Start" }: { id: string; label?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function onClick() {
    setPending(true);
    try {
      await startProcessing(id);
    } catch {
      // 409 = already processing; refreshing reflects the real state either way.
    } finally {
      router.refresh();
      setPending(false);
    }
  }

  return (
    <Button variant="primary" onClick={onClick} disabled={pending}>
      {pending ? "Starting…" : label}
    </Button>
  );
}
```

- [ ] **Step 2: Write `ProcessingPoller`**

Create `apps/web/components/snapshot/ProcessingPoller.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getSnapshot } from "@gulp/api-client";
import { isProcessing } from "@/lib/pack";

const INTERVAL_MS = 3000;
const MAX_POLLS = 40; // ~2 minutes, then give up (user can refresh)

export function ProcessingPoller({ id }: { id: string }) {
  const router = useRouter();
  useEffect(() => {
    let polls = 0;
    let stopped = false;
    const timer = setInterval(async () => {
      polls += 1;
      try {
        const snap = await getSnapshot(id);
        if (!isProcessing(snap.status)) {
          clearInterval(timer);
          if (!stopped) router.refresh();
        }
      } catch {
        // transient — keep polling until the cap
      }
      if (polls >= MAX_POLLS) clearInterval(timer);
    }, INTERVAL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [id, router]);
  return null;
}
```

- [ ] **Step 3: Write `ReaderToggle`**

Create `apps/web/components/snapshot/ReaderToggle.module.css`:

```css
.bar { display: flex; gap: 6px; margin-bottom: 20px; }
.tab { border: 1px solid var(--border, #ddd); background: none; border-radius: 999px; padding: 3px 12px; font-size: 13px; color: var(--text-muted, #777); }
.active { border-color: var(--text-1); color: var(--text-1); font-weight: 500; }
.layout { display: flex; gap: 32px; align-items: flex-start; }
.main { flex: 1; min-width: 0; }
.rail { width: 220px; flex-shrink: 0; }
.original { max-width: 680px; white-space: pre-wrap; line-height: 22px; color: var(--text-1); }
```

Create `apps/web/components/snapshot/ReaderToggle.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { PackOut } from "@gulp/api-client";
import { PackReport } from "./PackReport";
import { FacetRail } from "./FacetRail";
import styles from "./ReaderToggle.module.css";

export function ReaderToggle({ pack, original }: { pack: PackOut; original: string | null }) {
  const [view, setView] = useState<"pack" | "original">("pack");
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
          className={`${styles.tab} ${view === "original" ? styles.active : ""}`}
          onClick={() => setView("original")}
          disabled={!original}
        >
          Original
        </button>
      </div>
      {view === "pack" ? (
        <div className={styles.layout}>
          <div className={styles.main}>
            <PackReport pack={pack} />
          </div>
          <div className={styles.rail}>
            <FacetRail facets={pack.facets} />
          </div>
        </div>
      ) : (
        <div className={styles.original}>{original ?? "No original text stored."}</div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify the islands type-check**

Run: `pnpm --filter @gulp/web exec tsc --noEmit`
Expected: no type errors. (No DOM test here — these are interactive client islands; their logic lives in `lib/pack.ts` (tested) and they're exercised by `next build` + manual use. The `react-dom` `renderToStaticMarkup` would render initial state but interaction needs a browser.)

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/StartButton.tsx apps/web/components/snapshot/ProcessingPoller.tsx apps/web/components/snapshot/ReaderToggle.tsx apps/web/components/snapshot/ReaderToggle.module.css
git commit -m "feat(web): Start / Poller / ReaderToggle client islands"
```

---

### Task 4: Detail page + Inbox wiring

**Files:**
- Create: `apps/web/app/snapshots/[id]/page.tsx`, `apps/web/components/snapshot/SnapshotStatusView.module.css`
- Modify: `apps/web/components/inbox/InboxRow.tsx`

**Interfaces:**
- Consumes: `getSnapshot`, `getPack` (`@gulp/api-client`); `ReaderToggle`, `StartButton`, `ProcessingPoller` (Tasks 2–3); `notFound` (`next/navigation`).
- Produces: route `/snapshots/[id]` (force-dynamic RSC) branching on `snapshot.status`; `InboxRow` linking title → `/snapshots/[id]` and rendering a `StartButton` for `unprocessed`/`needs_attention`.

- [ ] **Step 1: Write the status-view styles**

Create `apps/web/components/snapshot/SnapshotStatusView.module.css`:

```css
.page { padding: 24px; max-width: 960px; }
.back { font-size: 13px; color: var(--text-muted, #777); margin-bottom: 12px; display: inline-block; }
.title { margin-bottom: 6px; }
.source { color: var(--text-muted, #777); margin-bottom: 20px; }
.skeleton { height: 12px; background: var(--surface-2, #eee); border-radius: 6px; margin: 10px 0; animation: pulse 1.4s ease-in-out infinite; }
.skeleton.short { width: 50%; }
@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.5 } }
.banner { border-left: 3px solid var(--warning, #d98a00); background: var(--warning-tint, #fff7e6); padding: 12px 14px; border-radius: 6px; margin: 16px 0; }
.actions { display: flex; gap: 12px; align-items: center; margin-top: 16px; }
.open { font-size: 13px; color: var(--accent, #2f6bff); }
```

- [ ] **Step 2: Write the detail page**

Create `apps/web/app/snapshots/[id]/page.tsx`:

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPack, getSnapshot } from "@gulp/api-client";
import { ReaderToggle } from "@/components/snapshot/ReaderToggle";
import { StartButton } from "@/components/snapshot/StartButton";
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

  const source = snap.origin_url ? new URL(snap.origin_url).host : "Note";

  return (
    <div className={styles.page}>
      <Link href="/inbox" className={styles.back}>← Inbox</Link>
      <h1 className={`t-title-l ${styles.title}`}>{snap.title}</h1>
      <p className={`t-data ${styles.source}`}>{source}</p>

      {snap.status === "unprocessed" && (
        <div className={styles.actions}>
          <StartButton id={id} />
          {snap.origin_url && (
            <a className={styles.open} href={snap.origin_url} target="_blank" rel="noreferrer">Open original</a>
          )}
        </div>
      )}

      {snap.status === "processing" && (
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
            <StartButton id={id} label="▶ Retry" />
            {snap.origin_url && (
              <a className={styles.open} href={snap.origin_url} target="_blank" rel="noreferrer">Open original</a>
            )}
          </div>
        </>
      )}

      {(snap.status === "ready" || snap.status === "in_library" || snap.status === "awaiting_review") &&
        (await renderPack(id, snap.content_body))}
    </div>
  );
}

async function renderPack(id: string, original: string | null) {
  const pack = await getPack(id);
  if (!pack) {
    return <p className="t-data" style={{ color: "var(--text-muted, #777)" }}>Pack not available.</p>;
  }
  return <ReaderToggle pack={pack} original={original} />;
}
```

- [ ] **Step 3: Wire the Inbox row**

Replace `apps/web/components/inbox/InboxRow.tsx` with (adds the detail link + a Start affordance; keeps the existing status label + open-original):

```tsx
import Link from "next/link";
import type { Snapshot } from "@gulp/api-client";
import { ObjectGlyph } from "@/components/ui/ObjectGlyph";
import { StartButton } from "@/components/snapshot/StartButton";
import styles from "./InboxRow.module.css";

function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  if (status === "unprocessed") return "Not started";
  return "Ready";
}

export function InboxRow({ item }: { item: Snapshot }) {
  const source = item.origin_url ? new URL(item.origin_url).host : "Note";
  const startable = item.status === "unprocessed" || item.status === "needs_attention";
  return (
    <li className={styles.row}>
      <ObjectGlyph type="snapshot" />
      <div className={styles.text}>
        <Link href={`/snapshots/${item.id}`} className={styles.title}>{item.title}</Link>
        <span className={`t-data ${styles.meta}`}>{source}</span>
      </div>
      {startable ? (
        <StartButton id={item.id} label="▶ Start" />
      ) : (
        <span className={styles.status}>{statusLabel(item.status)}</span>
      )}
    </li>
  );
}
```

- [ ] **Step 4: Type-check + build + run the web test suite**

Run: `pnpm --filter @gulp/web exec vitest run`
Expected: PASS (the Task 1 + Task 2 tests).

Run: `pnpm --filter @gulp/web build`
Expected: builds with no type errors; the `/snapshots/[id]` route appears in the route list (as a dynamic route).

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/snapshots apps/web/components/snapshot/SnapshotStatusView.module.css apps/web/components/inbox/InboxRow.tsx
git commit -m "feat(web): snapshot detail reader page + Inbox Start/link"
```

---

## Self-Review

**Spec coverage** (against the design spec §2 Plan B + §3/§4):
- Detail page with status branches (`unprocessed`→Start, `processing`→skeleton+poller, `ready`→reader, `needs_attention`→banner+Retry) → Task 4 ✓.
- Report-first layout: `PackReport` main column + `FacetRail` rail + `ReaderToggle` Pack/Original → Tasks 2–3 ✓.
- ▶ Start on detail + Inbox row; Inbox rows link to detail → Tasks 3–4 ✓.
- Light polling (`ProcessingPoller`, ~3s, bounded) → Task 3 ✓.
- Data flow `processing → poll → router.refresh() → RSC re-fetch` → Tasks 3–4 ✓.
- Error/empty: `getSnapshot` failure → `notFound()`; `getPack` null while ready → "Pack not available" soft state; `needs_attention` banner; Start 409 swallowed + refresh → Tasks 3–4 ✓.
- Testing: pure logic (vitest) + presentational (`renderToStaticMarkup`) + build; interactive eyeballed → Tasks 1–2, 4 ✓.
- **Deferred:** cards section (no cards yet); per-block citation chips; on-demand figures (figure blocks render their text); mobile parity; `getPack` distinguishing 404 vs 5xx (carry-forward from Plan A — currently all errors → "not available").

**Placeholder scan:** none — every step carries concrete code/commands.

**Type consistency:** `groupFacets`/`isProcessing`/`FacetGroup` (Task 1) are used identically in `FacetRail` (Task 2) and `ProcessingPoller` (Task 3). `PackReport({ pack })`, `FacetRail({ facets })`, `ReaderToggle({ pack, original })`, `StartButton({ id, label? })`, `ProcessingPoller({ id })` signatures match across their definitions, the test, the page, and the Inbox row. `getSnapshot`/`getPack`/`startProcessing` are the Plan-A helpers (already merged). The `/snapshots/[id]` route path matches the `Link href` in `InboxRow` and the `← Inbox` back link.
