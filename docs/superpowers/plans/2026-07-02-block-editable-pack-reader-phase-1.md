# Block-Editable Pack Reader — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the read-only knowledge-pack reader into a systematic,
`docs/03`-compliant document and lay the block-wise scaffolding (stable ids +
per-block cell wrapper) that Phases 2–3 build editing and chat on.

**Architecture:** Backend exposes stable `id`s on sections and blocks in the
`PackOut` read contract (no DB change — the rows already have ids). The web
reader wraps each block in a `BlockCell` keyed by that id, then gets a full
visual pass using the existing `@gulp/ui` tokens and global text-role classes.
No editing, no mutation endpoints, no chat in this phase.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy (`services/api`, `services/shared`);
OpenAPI-generated `@gulp/api-client`; Next.js 15 App Router + React 19 + CSS
Modules (`apps/web`); Vitest (web) + pytest (api).

## Global Constraints

- **The data model is the contract** (`docs/04 §2.5`): Python `app/schemas` is the
  source of truth. After changing `services/api/app/schemas`, run `just gen-client`.
- **Web talks to the backend only through `@gulp/api-client`** — never hand-write
  fetch types (`apps/web/CLAUDE.md`).
- **Visual primitives/tokens come from `@gulp/ui`** — never redefine tokens
  locally (`apps/web/CLAUDE.md`). CSS Modules only; **no Tailwind**.
- **No heavy new dependencies.** BlockNote / TipTap / Lexical are explicitly not
  adopted (spec "Decisions locked in").
- **API layering** (`services/api/CLAUDE.md`): routers thin, logic in
  `app/services`, persistence in `gulp_shared`.
- **Reading measure** = `var(--measure)` (720px, `docs/03 §5.2`).
- **Write all code, comments, and docs in English** (CLAUDE.md rule 6).
- Quality gates: `just lint` and `just test` must pass before a task is done.

**Phase note (refinement of the spec's phase labeling):** the spec lists the
two-column docked workbench under Phase 1. To avoid shipping a permanently-empty
right rail, this plan builds only the centered reading column here and defers the
docked two-column layout to **Phase 3**, where the `ChatPanel` fills the rail.
Phase 1 still delivers the visual redesign and block scaffolding.

---

### Task 1: Expose section & block ids in the `PackOut` contract

**Files:**
- Modify: `services/api/app/schemas/pack.py`
- Modify: `services/api/app/services/pack.py:22-36`
- Test: `services/api/tests/test_pack_router.py`
- Regenerate: `packages/api-client/openapi.json`, `packages/api-client/src/schema.gen.ts`

**Interfaces:**
- Consumes: existing ORM rows `PackSection.id`, `PackBlock.id` (uuid PKs from
  `Base`).
- Produces: `PackOut.sections[].id: string (uuid)` and
  `PackOut.sections[].blocks[].id: string (uuid)` in the generated client — the
  stable ids Phase 2 (mutations) and Phase 3 (chat anchors) address blocks by.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_pack_router.py`:

```python
def test_get_pack_exposes_section_and_block_ids(client, db) -> None:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", key_insight="ki",
                         core_contributions=["c1"], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                      data={"content": "hello"}, position=0)
    db.add(block)
    db.commit()
    sec_id, block_id = str(sec.id), str(block.id)

    r = client.get(f"/snapshots/{snap.id}/pack")
    assert r.status_code == 200
    body = r.json()
    assert body["sections"][0]["id"] == sec_id
    assert body["sections"][0]["blocks"][0]["id"] == block_id
    assert body["sections"][0]["blocks"][0]["type"] == "prose"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/api/tests/test_pack_router.py::test_get_pack_exposes_section_and_block_ids -v`
Expected: FAIL — response JSON has no `id` key on section/block (`KeyError`/assert).

- [ ] **Step 3: Add `id` to the schema block variants and section**

In `services/api/app/schemas/pack.py`, add `id: uuid.UUID` as the first field of
each block variant and of `PackSectionOut` (`uuid` is already imported):

```python
class ProseBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["prose"] = "prose"
    content: str


class FormulaBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["formula"] = "formula"
    latex: str
    explanation: str


class TableBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class FigureBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["figure"] = "figure"
    label: str
    explanation: str


class ListBlockOut(BaseModel):
    id: uuid.UUID
    type: Literal["list"] = "list"
    items: list[str]
    ordered: bool = False
```

And:

```python
class PackSectionOut(BaseModel):
    id: uuid.UUID
    heading: str | None
    blocks: list[BlockOut]
```

- [ ] **Step 4: Emit the ids in the serializer**

In `services/api/app/services/pack.py`, include `id` in each block dict and pass
`id=section.id` to `PackSectionOut`:

```python
        blocks = [
            {"id": b.id, "type": b.block_type.value, **(b.data or {})}
            for b in db.scalars(
                select(PackBlock)
                .where(PackBlock.section_id == section.id, PackBlock.deleted_at.is_(None))
                .order_by(PackBlock.position)
            )
        ]
        sections.append(PackSectionOut(id=section.id, heading=section.heading, blocks=blocks))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest services/api/tests/test_pack_router.py -v`
Expected: PASS (the new test plus the existing pack-router tests).

- [ ] **Step 6: Regenerate the API client**

Run: `just gen-client`
Expected: `packages/api-client/src/schema.gen.ts` now shows `id: string` on
`PackSectionOut` and every block variant; `openapi.json` updated.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/schemas/pack.py services/api/app/services/pack.py \
        services/api/tests/test_pack_router.py \
        packages/api-client/openapi.json packages/api-client/src/schema.gen.ts
git commit -m "feat(api): expose section/block ids in PackOut contract"
```

---

### Task 2: Wrap blocks in `BlockCell` keyed by id (web scaffolding)

**Files:**
- Create: `apps/web/components/snapshot/BlockCell.tsx`
- Create: `apps/web/components/snapshot/BlockCell.module.css`
- Modify: `apps/web/components/snapshot/PackReport.tsx:89-123`
- Test: `apps/web/components/snapshot/PackReport.test.tsx`

**Interfaces:**
- Consumes: `PackOut.sections[].id`, `PackOut.sections[].blocks[].id` (Task 1).
- Produces: `BlockCell({ id: string, children: React.ReactNode })` rendering a
  `<div class=… data-block-id={id}>` wrapper — the stable per-block DOM anchor
  Phase 2 (toolbar/editors) and Phase 3 (chat `💬`) attach to.

- [ ] **Step 1: Write the failing test**

The `PackOut` type now requires `id` on sections/blocks, so first update the
fixture in `apps/web/components/snapshot/PackReport.test.tsx` to add ids, then add
the new assertion. Replace the `pack` fixture and add one test:

```tsx
const pack: PackOut = {
  snapshot_id: "00000000-0000-0000-0000-000000000001",
  status: "ready",
  title: "BERT",
  core_contributions: ["MLM enables **bidirectionality**."],
  key_insight: "Change the objective.",
  sections: [
    {
      id: "00000000-0000-0000-0000-0000000000a1",
      heading: "Math",
      blocks: [
        { id: "00000000-0000-0000-0000-0000000000b1", type: "prose", content: "Loss is $L=-\\sum_i y_i$ here." },
        { id: "00000000-0000-0000-0000-0000000000b2", type: "formula", latex: "E=mc^2", explanation: "Mass-energy." },
        { id: "00000000-0000-0000-0000-0000000000b3", type: "table", headers: ["Model", "F1"], rows: [["BERT", "93.2"]], caption: "Results" },
        { id: "00000000-0000-0000-0000-0000000000b4", type: "list", ordered: false, items: ["lr=1e-4"] },
        { id: "00000000-0000-0000-0000-0000000000b5", type: "list", ordered: true, items: ["step one"] },
        { id: "00000000-0000-0000-0000-0000000000b6", type: "figure", label: "Figure 1", explanation: "Architecture overview." },
      ],
    },
  ],
  references: [{ citation: "Vaswani 2017", why_interesting: "Transformer." }],
};
```

Add this test inside the `describe("PackReport", …)` block:

```tsx
  it("wraps each block in a cell carrying its stable id", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain('data-block-id="00000000-0000-0000-0000-0000000000b1"');
    expect(html).toContain('data-block-id="00000000-0000-0000-0000-0000000000b6"');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: FAIL — the new test's `data-block-id` assertion fails (no wrapper yet).

- [ ] **Step 3: Create `BlockCell.tsx`**

```tsx
import React from "react";
import styles from "./BlockCell.module.css";

// Per-block wrapper. Phase 1 only carries the stable id; Phases 2–3 add the
// hover toolbar, edit mode, and chat trigger onto this same cell.
export function BlockCell({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <div className={styles.cell} data-block-id={id}>
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Create `BlockCell.module.css` (minimal — Task 3 adds hover styles)**

```css
.cell {
  position: relative;
}
```

- [ ] **Step 5: Render blocks through `BlockCell`, keyed by id**

In `apps/web/components/snapshot/PackReport.tsx`, add the import and change the
sections map to key by `section.id` and wrap each block in `BlockCell`:

```tsx
import { BlockCell } from "./BlockCell";
```

```tsx
      {pack.sections.map((section) => (
        <section key={section.id} className={styles.section}>
          {section.heading && <h2 className={styles.heading}>{section.heading}</h2>}
          {section.blocks.map((block) => (
            <BlockCell key={block.id} id={block.id}>
              <BlockView block={block} />
            </BlockCell>
          ))}
        </section>
      ))}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: PASS (both the existing render tests and the new cell test).

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/snapshot/BlockCell.tsx \
        apps/web/components/snapshot/BlockCell.module.css \
        apps/web/components/snapshot/PackReport.tsx \
        apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): wrap pack blocks in BlockCell keyed by stable id"
```

---

### Task 3: Visual redesign of the pack reader (docs/03 web register)

**Files:**
- Modify: `apps/web/components/snapshot/PackReport.tsx:89-137`
- Modify: `apps/web/components/snapshot/PackReport.module.css` (full rewrite)
- Modify: `apps/web/components/snapshot/BlockCell.module.css`
- Test: `apps/web/components/snapshot/PackReport.test.tsx`

**Interfaces:**
- Consumes: the `BlockCell` wrapper (Task 2) and global text-role classes from
  `apps/web/app/globals.css` (`t-display`, `t-title-l`, `t-title-m`, `t-body-l`,
  `t-label`, `t-data`) and `@gulp/ui` tokens.
- Produces: no API surface change — a redesigned render. Section blocks stay
  wrapped in `BlockCell` so Phase 2/3 anchors are preserved.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/components/snapshot/PackReport.test.tsx` (the `pack` fixture from
Task 2 is reused):

```tsx
  it("applies docs/03 type roles: serif/large title, mono overlines, section headings", () => {
    const html = renderToStaticMarkup(<PackReport pack={pack} />);
    expect(html).toContain("t-display");        // pack title in Instrument Serif
    expect(html).toContain("t-label");          // mono uppercase overlines
    expect(html).toContain("CORE CONTRIBUTIONS");
    expect(html).toContain("KEY INSIGHT");
    expect(html).toContain("t-title-m");        // section heading role
    expect(html).toContain("FURTHER READING");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: FAIL — current markup uses module `styles.heading`/`styles.title`, not
the global text-role classes or the mono overlines.

- [ ] **Step 3: Rewrite the render to use text roles, overlines, and distinct section roles**

Replace the `PackReport` function body in
`apps/web/components/snapshot/PackReport.tsx` with:

```tsx
export function PackReport({ pack }: { pack: PackOut }) {
  return (
    <article className={styles.report}>
      <h1 className={`t-display ${styles.title}`}>{pack.title}</h1>

      {pack.core_contributions.length > 0 && (
        <section className={styles.block}>
          <p className={`t-label ${styles.overline}`}>CORE CONTRIBUTIONS</p>
          <ul className={styles.contribList}>
            {pack.core_contributions.map((c, i) => (
              <li key={i}>
                <Md>{c}</Md>
              </li>
            ))}
          </ul>
        </section>
      )}

      {pack.key_insight && (
        <section className={styles.insight}>
          <p className={`t-label ${styles.overline}`}>KEY INSIGHT</p>
          <div className={`t-body-l ${styles.insightBody}`}>
            <Md>{pack.key_insight}</Md>
          </div>
        </section>
      )}

      {pack.sections.map((section) => (
        <section key={section.id} className={styles.section}>
          {section.heading && <h2 className={`t-title-m ${styles.heading}`}>{section.heading}</h2>}
          {section.blocks.map((block) => (
            <BlockCell key={block.id} id={block.id}>
              <BlockView block={block} />
            </BlockCell>
          ))}
        </section>
      ))}

      {pack.references.length > 0 && (
        <section className={styles.references}>
          <p className={`t-label ${styles.overline}`}>FURTHER READING</p>
          <ul className={styles.refList}>
            {pack.references.map((r, i) => (
              <li key={i}>
                <span className={styles.refCitation}>{r.citation}</span>
                <span className={styles.refWhy}>{r.why_interesting}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}
```

Note: the overline text is written **uppercase in the markup** (`CORE
CONTRIBUTIONS` / `KEY INSIGHT` / `FURTHER READING`) so `renderToStaticMarkup`
emits those literal strings for the test; the `t-label` class's
`text-transform: uppercase` is then just a visual no-op.

- [ ] **Step 4: Rewrite `PackReport.module.css` to the docs/03 web register**

Replace the entire file with:

```css
/* Pack reader — docs/03 web register: near-grayscale slate, hairline structure,
 * type-led hierarchy, 4px spacing base. Tokens from @gulp/ui. */
.report {
  max-width: var(--measure);
  margin: 0 auto;
}

.title {
  margin-bottom: var(--space-6);
  color: var(--text-1);
}

.overline {
  margin-bottom: var(--space-2);
}

.block,
.insight,
.references {
  margin-bottom: var(--space-8);
}

.section {
  margin-bottom: var(--space-8);
  padding-top: var(--space-6);
  border-top: 1px solid var(--border);
}

.heading {
  margin-bottom: var(--space-3);
  color: var(--text-1);
}

/* Key insight — the single most transferable idea, set apart as a lead. */
.insight {
  padding: var(--space-4) var(--space-5);
  background: var(--fill);
  border-radius: var(--radius-md);
  border-left: 2px solid var(--blue-600);
}
.insightBody {
  color: var(--text-1);
}

.contribList {
  margin: 0;
  padding-left: var(--space-5);
  line-height: 24px;
}
.contribList li {
  margin-bottom: var(--space-1);
}

.references .refList {
  list-style: none;
  margin: 0;
  padding: 0;
}
.references .refList li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border);
}
.refCitation {
  font-weight: 600;
  color: var(--text-1);
}
.refWhy {
  color: var(--text-2);
}
```

- [ ] **Step 5: Add per-block styling + hover affordance scaffold in `BlockCell.module.css`**

Replace `apps/web/components/snapshot/BlockCell.module.css` with:

```css
/* One block = one cell. A left gutter reserves room for the Phase-2 toolbar and
 * the Phase-3 chat trigger; hover gives a subtle, functional highlight
 * (docs/03: quiet, hairline, no ornament). */
.cell {
  position: relative;
  padding: var(--space-2) var(--space-3);
  margin-left: calc(-1 * var(--space-3));
  border-radius: var(--radius-md);
  transition: background 140ms cubic-bezier(0.2, 0, 0, 1);
}
.cell:hover {
  background: var(--fill);
}

/* Block-internal typography (moved here from the old PackReport styles). */
.cell :global(figure) {
  margin: var(--space-3) 0;
  overflow-x: auto;
}
.cell :global(table) {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.cell :global(th),
.cell :global(td) {
  border: 1px solid var(--border);
  padding: var(--space-1) var(--space-2);
  text-align: left;
}
.cell :global(figcaption) {
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-2);
}
```

Note: `BlockView` still references `styles.prose`, `styles.formula`, etc. from
`PackReport.module.css`. Keep those class names present in the rewritten
`PackReport.module.css` so `BlockView` compiles. Add these to the CSS from Step 4:

```css
.prose { line-height: 24px; }
.prose > :global(*) + :global(*) { margin-top: var(--space-3); }
.formula { text-align: center; }
.explanation {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-2);
  margin-top: var(--space-1);
}
.tableWrap {}
.table {}
.caption {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-2);
  margin-top: var(--space-1);
}
.figure {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
}
.figureLabel {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: var(--space-1);
}
.list { line-height: 24px; margin: 0; padding-left: var(--space-5); }
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: PASS (all three tests: content, cell ids, type roles).

- [ ] **Step 7: Visual verification (manual, no commit)**

Run: `just web`, open a snapshot in `ready` state
(`http://localhost:3000/snapshots/<id>`), and confirm: serif title, mono
overlines, the key-insight lead card, hairline section separators, block hover
highlight, and readable tables/formulas at the 720px measure. (Backend/infra must
be up: `just up` + `just api` + `just worker`, or `just dev`.)

- [ ] **Step 8: Run the full quality gates**

Run: `just lint` then `just test`
Expected: both PASS.

- [ ] **Step 9: Commit**

```bash
git add apps/web/components/snapshot/PackReport.tsx \
        apps/web/components/snapshot/PackReport.module.css \
        apps/web/components/snapshot/BlockCell.module.css \
        apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): redesign pack reader to the docs/03 web register"
```

---

## Self-Review

**Spec coverage (Phase 1 slice):**
- Contract: add `id` to `PackSectionOut` + block union, emit in serializer, regen
  client → Task 1. ✔
- Web keys blocks by `id` → Task 2. ✔
- `BlockCell` wrapper (scaffolding for Phase 2/3) → Task 2. ✔
- Visual redesign per `docs/03` (type roles, hairlines, spacing, overlines,
  key-insight lead, references, block hover, KaTeX/table polish) → Task 3. ✔
- Reading measure `var(--measure)` → Task 3 CSS. ✔
- Docked two-column workbench → **deferred to Phase 3** (documented in the Phase
  note; avoids an empty rail). ✔ (intentional, called out)
- Phase 2 (editing/add/delete) and Phase 3 (chat) → separate future plans. ✔

**Placeholder scan:** No TBD/TODO; every code step shows full code; test steps
show real assertions and exact run commands. ✔

**Type consistency:** `BlockCell({ id, children })` defined in Task 2 and used
unchanged in Task 3. `data-block-id` attribute name is identical across Task 2
markup, Task 2 test, and Task 3. Schema field `id: uuid.UUID` (Task 1) → generated
`id: string` consumed as `block.id`/`section.id` (Tasks 2–3). Global classes
(`t-display`, `t-label`, `t-title-m`, `t-body-l`) exist in `globals.css`. Module
classes referenced by `BlockView` (`prose`, `formula`, `explanation`, `tableWrap`,
`table`, `caption`, `figure`, `figureLabel`, `list`) are all present in the
rewritten `PackReport.module.css`. ✔

## Notes for Phases 2 & 3 (not this plan)

- **Phase 2:** mutation endpoints (`PATCH`/`POST`/`DELETE`), per-type editors,
  `BlockToolbar` (`⋯` + drag), `AddBlockMenu` (`+`), pack reader becomes a client
  island with optimistic updates. Gets its own plan.
- **Phase 3:** relocate the LLM layer to `services/shared`, add `PackBlockMessage`
  model + migration + messages endpoints with grounding, build the docked
  two-column workbench + `ChatPanel`. Gets its own plan.
