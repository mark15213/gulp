# Block-Editable Pack Reader — Phase 2b: Editing UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the read-only pack reader into a block-wise editable document — edit each block in a type-appropriate editor, delete, reorder (move up/down), and insert new blocks — driving the Phase 2a mutation endpoints with optimistic updates.

**Architecture:** `PackReport` becomes a client island holding the pack in `useState`. Reads render through the extracted `BlockView`; a per-block `BlockCell` toggles into a `BlockEditor` (dispatched per type) and shows a hover `BlockToolbar` (edit/delete/move) and an `AddBlockMenu` (`+` insert). Mutations call the `@gulp/api-client` helpers from Phase 2a; edit/delete/move update local state optimistically and roll back with an error banner on failure; insert awaits the server (needs the new id) then splices in. Pure state transforms live in `lib/packEdit.ts` and are unit-tested in isolation.

**Tech Stack:** Next.js 15 + React 19 client components, CSS Modules + `@gulp/ui` tokens, `@gulp/api-client` (Phase 2a helpers), Vitest + @testing-library/react (interaction tests).

## Global Constraints

- **Depends on Phase 2a** (`docs/superpowers/plans/2026-07-02-block-editable-pack-reader-phase-2a-mutation-api.md`): it exports `updateBlock(snapshotId, blockId, body)`, `createBlock(snapshotId, sectionId, body)`, `deleteBlock(snapshotId, blockId)` and types `PackBlockOut`, `BlockUpdateBody`, `BlockCreateBody`. Do not start 2b until 2a is merged/available.
- **Web talks to the backend only through `@gulp/api-client`** — never hand-write fetch types (`apps/web/CLAUDE.md`).
- **Tokens/primitives from `@gulp/ui`**; CSS Modules only, NO Tailwind, no local token redefinition. Reuse `@/components/ui/Button`.
- **No heavy runtime deps** (no BlockNote/TipTap/Lexical). `@testing-library/react` + `@testing-library/user-event` are dev/test-only additions (vitest already runs `environment: "jsdom"`).
- **State: client island, no state library.** `PackReport` holds `useState<PackOut>`; mutations are optimistic (edit/delete/move) with rollback + a dismissible error banner; insert awaits the server response then splices. Copy never blames the user (`docs/03 §2.7`).
- **Reorder is move up/down only** (via `updateBlock({position})`); drag-and-drop is deferred (YAGNI — up/down covers reorder reliably).
- **Block `type` may change on edit** (the editor emits a full `BlockWrite`); the per-type editors edit within a type. Section-heading editing is out of scope.
- **Not built:** a "regenerate" re-run button on a `ready` pack — the current UI never exposes re-run once ready, so the "re-run wipes edits" confirm has no reachable trigger. If a Regenerate button is added later, it must carry that confirm.
- Code/comments in English only.

**Environment (carry into every task):**
- Web tests: `pnpm --filter @gulp/web exec vitest run <path>` (vitest is jsdom-global; import `describe/it/expect/vi` from `vitest`).
- Web typecheck: `pnpm --filter @gulp/web exec tsc --noEmit`.
- The working tree has PRE-EXISTING unrelated uncommitted changes under `services/shared` / `services/worker` (+ an untracked `.zip` and a worker migration). Stage ONLY each task's exact files; never `git add .`/`-A`.
- Do not run repo-root `just lint`/`just test` (documented pre-existing breakage). See [[api-tests-per-package]].

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `apps/web/lib/packEdit.ts` (+ `.test.ts`) | pure PackOut transforms + empty-block factory | create |
| `apps/web/components/snapshot/Md.tsx` | markdown+KaTeX renderer (extracted) | create |
| `apps/web/components/snapshot/BlockView.tsx` | read renderer per type (extracted) | create |
| `apps/web/components/snapshot/editors/EditorShell.tsx` | Save/Cancel frame | create |
| `apps/web/components/snapshot/editors/{Prose,Formula,Figure,List,Table}Editor.tsx` | per-type editors | create |
| `apps/web/components/snapshot/editors/BlockEditor.tsx` | type→editor dispatcher | create |
| `apps/web/components/snapshot/BlockToolbar.tsx` | edit/delete/move controls | create |
| `apps/web/components/snapshot/AddBlockMenu.tsx` | `+` insert with type picker | create |
| `apps/web/components/snapshot/Editing.module.css` | shared editing styles | create |
| `apps/web/components/snapshot/BlockCell.tsx` | view/edit toggle + toolbar + add-menu | rewrite |
| `apps/web/components/snapshot/PackReport.tsx` | client island: state + mutation handlers | rewrite |
| `apps/web/package.json` + repo `pnpm-lock.yaml` | add test-only deps | modify |

---

### Task 1: Pure state transforms — `lib/packEdit.ts`

**Files:**
- Create: `apps/web/lib/packEdit.ts`, `apps/web/lib/packEdit.test.ts`

**Interfaces:**
- Produces: `type BlockWrite = NonNullable<BlockUpdateBody["content"]>`; `type BlockType = PackBlockOut["type"]`; `replaceBlock(pack, sectionId, blockId, block): PackOut`; `removeBlock(pack, sectionId, blockId): PackOut`; `insertBlockAt(pack, sectionId, index, block): PackOut`; `moveBlock(pack, sectionId, blockId, newIndex): PackOut`; `emptyContent(type: BlockType): BlockWrite`. All transforms are pure and immutable.

- [ ] **Step 1: Write the failing test**

Create `apps/web/lib/packEdit.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { PackOut } from "@gulp/api-client";
import { emptyContent, insertBlockAt, moveBlock, removeBlock, replaceBlock } from "./packEdit";

const S = "00000000-0000-0000-0000-0000000000a1";
const B0 = "00000000-0000-0000-0000-0000000000b0";
const B1 = "00000000-0000-0000-0000-0000000000b1";

function pack(): PackOut {
  return {
    snapshot_id: "00000000-0000-0000-0000-000000000001",
    status: "ready",
    title: "T",
    core_contributions: [],
    key_insight: "",
    sections: [
      {
        id: S,
        heading: "H",
        blocks: [
          { id: B0, type: "prose", content: "b0" },
          { id: B1, type: "prose", content: "b1" },
        ],
      },
    ],
    references: [],
  };
}

describe("packEdit", () => {
  it("replaceBlock swaps the matching block, immutably", () => {
    const p0 = pack();
    const p1 = replaceBlock(p0, S, B0, { id: B0, type: "prose", content: "edited" });
    expect(p1).not.toBe(p0);
    expect(p1.sections[0].blocks[0]).toEqual({ id: B0, type: "prose", content: "edited" });
    expect(p0.sections[0].blocks[0].content).toBe("b0"); // original untouched
  });

  it("removeBlock drops the matching block", () => {
    const p1 = removeBlock(pack(), S, B0);
    expect(p1.sections[0].blocks.map((b) => b.id)).toEqual([B1]);
  });

  it("insertBlockAt inserts at the index", () => {
    const nb = { id: "new", type: "prose", content: "mid" } as const;
    const p1 = insertBlockAt(pack(), S, 1, nb);
    expect(p1.sections[0].blocks.map((b) => b.id)).toEqual([B0, "new", B1]);
  });

  it("moveBlock reorders within the section (clamped)", () => {
    const p1 = moveBlock(pack(), S, B0, 1);
    expect(p1.sections[0].blocks.map((b) => b.id)).toEqual([B1, B0]);
    const p2 = moveBlock(pack(), S, B0, 99);
    expect(p2.sections[0].blocks.map((b) => b.id)).toEqual([B1, B0]);
  });

  it("emptyContent returns a valid fresh write payload per type", () => {
    expect(emptyContent("prose")).toEqual({ type: "prose", content: "" });
    expect(emptyContent("list")).toEqual({ type: "list", items: [""], ordered: false });
    expect(emptyContent("table")).toEqual({
      type: "table",
      headers: ["Column 1", "Column 2"],
      rows: [["", ""]],
      caption: null,
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run lib/packEdit.test.ts`
Expected: FAIL — `Cannot find module './packEdit'`.

- [ ] **Step 3: Implement `lib/packEdit.ts`**

```ts
import type { BlockUpdateBody, PackBlockOut, PackOut } from "@gulp/api-client";

export type BlockWrite = NonNullable<BlockUpdateBody["content"]>;
export type BlockType = PackBlockOut["type"];

type Section = PackOut["sections"][number];

function mapSection(pack: PackOut, sectionId: string, fn: (s: Section) => Section): PackOut {
  return {
    ...pack,
    sections: pack.sections.map((s) => (s.id === sectionId ? fn(s) : s)),
  };
}

export function replaceBlock(
  pack: PackOut,
  sectionId: string,
  blockId: string,
  block: PackBlockOut,
): PackOut {
  return mapSection(pack, sectionId, (s) => ({
    ...s,
    blocks: s.blocks.map((b) => (b.id === blockId ? block : b)),
  }));
}

export function removeBlock(pack: PackOut, sectionId: string, blockId: string): PackOut {
  return mapSection(pack, sectionId, (s) => ({
    ...s,
    blocks: s.blocks.filter((b) => b.id !== blockId),
  }));
}

export function insertBlockAt(
  pack: PackOut,
  sectionId: string,
  index: number,
  block: PackBlockOut,
): PackOut {
  return mapSection(pack, sectionId, (s) => {
    const blocks = s.blocks.slice();
    const i = Math.max(0, Math.min(index, blocks.length));
    blocks.splice(i, 0, block);
    return { ...s, blocks };
  });
}

export function moveBlock(
  pack: PackOut,
  sectionId: string,
  blockId: string,
  newIndex: number,
): PackOut {
  return mapSection(pack, sectionId, (s) => {
    const blocks = s.blocks.filter((b) => b.id !== blockId);
    const moved = s.blocks.find((b) => b.id === blockId);
    if (!moved) return s;
    const i = Math.max(0, Math.min(newIndex, blocks.length));
    blocks.splice(i, 0, moved);
    return { ...s, blocks };
  });
}

export function emptyContent(type: BlockType): BlockWrite {
  switch (type) {
    case "prose":
      return { type: "prose", content: "" };
    case "formula":
      return { type: "formula", latex: "", explanation: "" };
    case "table":
      return { type: "table", headers: ["Column 1", "Column 2"], rows: [["", ""]], caption: null };
    case "figure":
      return { type: "figure", label: "", explanation: "" };
    case "list":
      return { type: "list", items: [""], ordered: false };
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run lib/packEdit.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/packEdit.ts apps/web/lib/packEdit.test.ts
git commit -m "feat(web): pure pack-edit state transforms + empty-block factory"
```

---

### Task 2: Extract `Md` + `BlockView` (read renderer)

**Files:**
- Create: `apps/web/components/snapshot/Md.tsx`, `apps/web/components/snapshot/BlockView.tsx`
- Modify: `apps/web/components/snapshot/PackReport.tsx` (import the extracted `BlockView`; drop the local copies)
- Test: `apps/web/components/snapshot/PackReport.test.tsx` (unchanged assertions must still pass)

**Interfaces:**
- Produces: `Md({ children: string })` (react-markdown + remark-gfm + remark-math + rehype-katex, imports the KaTeX CSS); `BlockView({ block: PackBlockOut })` rendering the five block types exactly as today. Both reused by PackReport and the editors.
- Consumes: `PackBlockOut` (api-client), `PackReport.module.css` (unchanged classes).

- [ ] **Step 1: Create `Md.tsx`**

```tsx
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export function Md({ children }: { children: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
      {children}
    </Markdown>
  );
}
```

- [ ] **Step 2: Create `BlockView.tsx`** (move the current `BlockView` verbatim; import `Md` and the CSS module)

```tsx
import type { PackBlockOut } from "@gulp/api-client";
import { Md } from "./Md";
import styles from "./PackReport.module.css";

export function BlockView({ block }: { block: PackBlockOut }) {
  switch (block.type) {
    case "prose":
      return (
        <div className={styles.prose}>
          <Md>{block.content}</Md>
        </div>
      );
    case "formula":
      return (
        <figure className={styles.formula}>
          <Md>{`$$\n${block.latex}\n$$`}</Md>
          <figcaption className={styles.explanation}>{block.explanation}</figcaption>
        </figure>
      );
    case "table":
      return (
        <figure className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {block.headers.map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {block.caption && <figcaption className={styles.caption}>{block.caption}</figcaption>}
        </figure>
      );
    case "figure":
      return (
        <figure className={styles.figure}>
          <div className={styles.figureLabel}>{block.label}</div>
          <div className={styles.explanation}>{block.explanation}</div>
        </figure>
      );
    case "list":
      return block.ordered ? (
        <ol className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ol>
      ) : (
        <ul className={styles.list}>
          {block.items.map((it, i) => (
            <li key={i}>
              <Md>{it}</Md>
            </li>
          ))}
        </ul>
      );
    default:
      return null;
  }
}
```

- [ ] **Step 3: Update `PackReport.tsx` to import them**

Delete the local `Md` and `BlockView` definitions and the now-unused markdown imports from `PackReport.tsx`, and add:

```tsx
import { BlockView } from "./BlockView";
```

Keep the rest of `PackReport.tsx` unchanged (it still renders `<BlockCell key={block.id} id={block.id}><BlockView block={block} /></BlockCell>` and the title/contributions/insight/references). Remove the now-unused `type Block = ...` alias if it is no longer referenced.

- [ ] **Step 4: Run the existing render tests to verify no behavior change**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: PASS (all 4 existing tests — identical rendered output).

- [ ] **Step 5: Typecheck + commit**

Run: `pnpm --filter @gulp/web exec tsc --noEmit` (exit 0), then:

```bash
git add apps/web/components/snapshot/Md.tsx apps/web/components/snapshot/BlockView.tsx \
        apps/web/components/snapshot/PackReport.tsx
git commit -m "refactor(web): extract Md + BlockView for reuse by editors"
```

---

### Task 3: Test-lib + editor shell + text editors (Prose/Formula/Figure)

**Files:**
- Modify: `apps/web/package.json`, repo `pnpm-lock.yaml`
- Create: `apps/web/components/snapshot/Editing.module.css`, `editors/EditorShell.tsx`, `editors/ProseEditor.tsx`, `editors/FormulaEditor.tsx`, `editors/FigureEditor.tsx`
- Test: `apps/web/components/snapshot/editors/textEditors.test.tsx`

**Interfaces:**
- Produces: `EditorShell({ onSave, onCancel, children })` renders `children` + Save (primary) / Cancel (ghost) buttons. Each editor: `({ block, onSave, onCancel }: { block: PackBlockOut; onSave: (content: BlockWrite) => void; onCancel: () => void })`, holds draft state seeded from `block`, emits a `BlockWrite` on Save.
- Consumes: `BlockWrite`, `PackBlockOut` (Task 1 / api-client); `Md` (Task 2) for previews; `@/components/ui/Button`.

- [ ] **Step 1: Add the test-only dependencies**

Run: `pnpm --filter @gulp/web add -D @testing-library/react @testing-library/user-event`
Expected: `apps/web/package.json` devDependencies gains both; repo `pnpm-lock.yaml` updates.

- [ ] **Step 2: Write the failing test**

Create `apps/web/components/snapshot/editors/textEditors.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PackBlockOut } from "@gulp/api-client";
import { ProseEditor } from "./ProseEditor";
import { FigureEditor } from "./FigureEditor";

describe("text editors", () => {
  it("ProseEditor seeds from the block and emits edited content on Save", async () => {
    const block: PackBlockOut = { id: "b", type: "prose", content: "old" };
    const onSave = vi.fn();
    render(<ProseEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const ta = screen.getByLabelText("Prose (Markdown)");
    expect(ta).toHaveValue("old");
    await userEvent.clear(ta);
    await userEvent.type(ta, "new text");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "prose", content: "new text" });
  });

  it("FigureEditor emits label + explanation", async () => {
    const block: PackBlockOut = { id: "b", type: "figure", label: "L", explanation: "E" };
    const onSave = vi.fn();
    render(<FigureEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "figure", label: "L", explanation: "E" });
  });

  it("Cancel calls onCancel", async () => {
    const onCancel = vi.fn();
    render(
      <ProseEditor block={{ id: "b", type: "prose", content: "x" }} onSave={vi.fn()} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
```

Note: `toHaveValue`/`toBeInTheDocument`-style matchers are not needed beyond `toHaveValue`; if `toHaveValue` is unavailable without `@testing-library/jest-dom`, assert `(ta as HTMLTextAreaElement).value === "old"` instead (do not add jest-dom).

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/textEditors.test.tsx`
Expected: FAIL — editor modules not found.

- [ ] **Step 4: Create `Editing.module.css`**

```css
.field { display: flex; flex-direction: column; gap: var(--space-1); margin-bottom: var(--space-3); }
.field label { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-2); }
.input, .textarea {
  border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-2);
  font: inherit; color: var(--text-1); background: var(--surface); width: 100%;
}
.textarea { min-height: 96px; resize: vertical; }
.actions { display: flex; gap: var(--space-2); margin-top: var(--space-2); }
.preview { margin-top: var(--space-2); padding: var(--space-2); background: var(--fill); border-radius: var(--radius-md); }
.toolbar { display: inline-flex; gap: var(--space-1); }
.iconBtn {
  border: 1px solid var(--border); background: var(--surface); border-radius: var(--radius-sm);
  padding: 2px 6px; font-size: 12px; color: var(--text-2); line-height: 1.4;
}
.iconBtn:hover { color: var(--text-1); border-color: var(--border-strong); }
.iconBtn:disabled { opacity: 0.4; cursor: default; }
.addBar { display: flex; align-items: center; gap: var(--space-2); min-height: var(--space-5); }
.addMenu { display: inline-flex; gap: var(--space-1); flex-wrap: wrap; }
.grid { border-collapse: collapse; }
.grid td { border: 1px solid var(--border); padding: 2px; }
.grid .input { border: none; }
```

- [ ] **Step 5: Create `EditorShell.tsx`**

```tsx
import React from "react";
import { Button } from "@/components/ui/Button";
import styles from "../Editing.module.css";

export function EditorShell({
  onSave,
  onCancel,
  children,
}: {
  onSave: () => void;
  onCancel: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      {children}
      <div className={styles.actions}>
        <Button variant="primary" onClick={onSave}>
          Save
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create `ProseEditor.tsx`, `FormulaEditor.tsx`, `FigureEditor.tsx`**

`ProseEditor.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { Md } from "../Md";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function ProseEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "prose" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [content, setContent] = useState(block.content);
  return (
    <EditorShell onSave={() => onSave({ type: "prose", content })} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="prose-src">Prose (Markdown)</label>
        <textarea
          id="prose-src"
          aria-label="Prose (Markdown)"
          className={styles.textarea}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </div>
      <div className={styles.preview}>
        <Md>{content}</Md>
      </div>
    </EditorShell>
  );
}
```

`FormulaEditor.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { Md } from "../Md";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function FormulaEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "formula" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [latex, setLatex] = useState(block.latex);
  const [explanation, setExplanation] = useState(block.explanation);
  return (
    <EditorShell
      onSave={() => onSave({ type: "formula", latex, explanation })}
      onCancel={onCancel}
    >
      <div className={styles.field}>
        <label htmlFor="formula-latex">LaTeX</label>
        <textarea
          id="formula-latex"
          aria-label="LaTeX"
          className={styles.textarea}
          value={latex}
          onChange={(e) => setLatex(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="formula-exp">Explanation</label>
        <input
          id="formula-exp"
          aria-label="Explanation"
          className={styles.input}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </div>
      <div className={styles.preview}>
        <Md>{`$$\n${latex}\n$$`}</Md>
      </div>
    </EditorShell>
  );
}
```

`FigureEditor.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function FigureEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "figure" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(block.label);
  const [explanation, setExplanation] = useState(block.explanation);
  return (
    <EditorShell onSave={() => onSave({ type: "figure", label, explanation })} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="figure-label">Label</label>
        <input
          id="figure-label"
          aria-label="Label"
          className={styles.input}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
      </div>
      <div className={styles.field}>
        <label htmlFor="figure-exp">Explanation</label>
        <textarea
          id="figure-exp"
          aria-label="Figure explanation"
          className={styles.textarea}
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
        />
      </div>
    </EditorShell>
  );
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/textEditors.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add apps/web/package.json pnpm-lock.yaml \
        apps/web/components/snapshot/Editing.module.css \
        apps/web/components/snapshot/editors/EditorShell.tsx \
        apps/web/components/snapshot/editors/ProseEditor.tsx \
        apps/web/components/snapshot/editors/FormulaEditor.tsx \
        apps/web/components/snapshot/editors/FigureEditor.tsx \
        apps/web/components/snapshot/editors/textEditors.test.tsx
git commit -m "feat(web): editor shell + prose/formula/figure editors (+ test-lib)"
```

---

### Task 4: Structural editors — `ListEditor` + `TableEditor`

**Files:**
- Create: `apps/web/components/snapshot/editors/ListEditor.tsx`, `editors/TableEditor.tsx`
- Test: `apps/web/components/snapshot/editors/structEditors.test.tsx`

**Interfaces:**
- Produces: `ListEditor`, `TableEditor` with the same `({ block, onSave, onCancel })` shape as Task 3; `ListEditor` emits `{ type: "list", items, ordered }`, `TableEditor` emits `{ type: "table", headers, rows, caption }`.
- Consumes: `EditorShell` (Task 3), `BlockWrite`, `PackBlockOut`, `Editing.module.css`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/editors/structEditors.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PackBlockOut } from "@gulp/api-client";
import { ListEditor } from "./ListEditor";
import { TableEditor } from "./TableEditor";

describe("structural editors", () => {
  it("ListEditor splits lines into items, drops blank lines, keeps ordered flag", async () => {
    const block: PackBlockOut = { id: "b", type: "list", items: ["one", "two"], ordered: false };
    const onSave = vi.fn();
    render(<ListEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const ta = screen.getByLabelText("List items (one per line)");
    await userEvent.clear(ta);
    await userEvent.type(ta, "a{enter}{enter}b");
    await userEvent.click(screen.getByLabelText("Ordered list"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({ type: "list", items: ["a", "b"], ordered: true });
  });

  it("TableEditor edits a cell and adds a row, then emits the grid", async () => {
    const block: PackBlockOut = {
      id: "b",
      type: "table",
      headers: ["H1", "H2"],
      rows: [["a", "b"]],
      caption: null,
    };
    const onSave = vi.fn();
    render(<TableEditor block={block} onSave={onSave} onCancel={vi.fn()} />);
    const cell = screen.getByLabelText("cell 0,0");
    await userEvent.clear(cell);
    await userEvent.type(cell, "X");
    await userEvent.click(screen.getByRole("button", { name: "Add row" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith({
      type: "table",
      headers: ["H1", "H2"],
      rows: [["X", "b"], ["", ""]],
      caption: null,
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/structEditors.test.tsx`
Expected: FAIL — editor modules not found.

- [ ] **Step 3: Create `ListEditor.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function ListEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "list" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(block.items.join("\n"));
  const [ordered, setOrdered] = useState(block.ordered);
  function save() {
    const items = text
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    onSave({ type: "list", items, ordered });
  }
  return (
    <EditorShell onSave={save} onCancel={onCancel}>
      <div className={styles.field}>
        <label htmlFor="list-items">List items (one per line)</label>
        <textarea
          id="list-items"
          aria-label="List items (one per line)"
          className={styles.textarea}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      <label>
        <input
          type="checkbox"
          aria-label="Ordered list"
          checked={ordered}
          onChange={(e) => setOrdered(e.target.checked)}
        />{" "}
        Ordered
      </label>
    </EditorShell>
  );
}
```

- [ ] **Step 4: Create `TableEditor.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function TableEditor({
  block,
  onSave,
  onCancel,
}: {
  block: Extract<PackBlockOut, { type: "table" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [headers, setHeaders] = useState<string[]>(block.headers);
  const [rows, setRows] = useState<string[][]>(block.rows.map((r) => r.slice()));
  const [caption, setCaption] = useState(block.caption ?? "");
  const cols = headers.length;

  function setHeader(c: number, v: string) {
    setHeaders(headers.map((h, i) => (i === c ? v : h)));
  }
  function setCell(r: number, c: number, v: string) {
    setRows(rows.map((row, ri) => (ri === r ? row.map((cell, ci) => (ci === c ? v : cell)) : row)));
  }
  function addRow() {
    setRows([...rows, Array(cols).fill("")]);
  }
  function addColumn() {
    setHeaders([...headers, `Column ${cols + 1}`]);
    setRows(rows.map((row) => [...row, ""]));
  }
  function save() {
    onSave({ type: "table", headers, rows, caption: caption.trim() ? caption : null });
  }

  return (
    <EditorShell onSave={save} onCancel={onCancel}>
      <table className={styles.grid}>
        <thead>
          <tr>
            {headers.map((h, c) => (
              <td key={c}>
                <input
                  className={styles.input}
                  aria-label={`header ${c}`}
                  value={h}
                  onChange={(e) => setHeader(c, e.target.value)}
                />
              </td>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (
                <td key={c}>
                  <input
                    className={styles.input}
                    aria-label={`cell ${r},${c}`}
                    value={cell}
                    onChange={(e) => setCell(r, c, e.target.value)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className={styles.actions}>
        <button type="button" className={styles.iconBtn} onClick={addRow}>
          Add row
        </button>
        <button type="button" className={styles.iconBtn} onClick={addColumn}>
          Add column
        </button>
      </div>
      <div className={styles.field}>
        <label htmlFor="table-caption">Caption</label>
        <input
          id="table-caption"
          aria-label="Caption"
          className={styles.input}
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
        />
      </div>
    </EditorShell>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/structEditors.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/snapshot/editors/ListEditor.tsx \
        apps/web/components/snapshot/editors/TableEditor.tsx \
        apps/web/components/snapshot/editors/structEditors.test.tsx
git commit -m "feat(web): list + table block editors"
```

---

### Task 5: `BlockEditor` dispatcher

**Files:**
- Create: `apps/web/components/snapshot/editors/BlockEditor.tsx`
- Test: `apps/web/components/snapshot/editors/BlockEditor.test.tsx`

**Interfaces:**
- Produces: `BlockEditor({ block, onSave, onCancel })` — dispatches on `block.type` to the matching Task 3/4 editor.
- Consumes: the five editors; `BlockWrite`, `PackBlockOut`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/editors/BlockEditor.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { PackBlockOut } from "@gulp/api-client";
import { BlockEditor } from "./BlockEditor";

describe("BlockEditor", () => {
  it("renders the table editor for a table block", () => {
    const block: PackBlockOut = { id: "b", type: "table", headers: ["H"], rows: [["a"]], caption: null };
    render(<BlockEditor block={block} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("cell 0,0")).toBeTruthy();
  });

  it("renders the prose editor for a prose block", () => {
    const block: PackBlockOut = { id: "b", type: "prose", content: "x" };
    render(<BlockEditor block={block} onSave={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByLabelText("Prose (Markdown)")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/BlockEditor.test.tsx`
Expected: FAIL — `BlockEditor` not found.

- [ ] **Step 3: Create `BlockEditor.tsx`**

```tsx
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { ProseEditor } from "./ProseEditor";
import { FormulaEditor } from "./FormulaEditor";
import { FigureEditor } from "./FigureEditor";
import { ListEditor } from "./ListEditor";
import { TableEditor } from "./TableEditor";

export function BlockEditor({
  block,
  onSave,
  onCancel,
}: {
  block: PackBlockOut;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  switch (block.type) {
    case "prose":
      return <ProseEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "formula":
      return <FormulaEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "figure":
      return <FigureEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "list":
      return <ListEditor block={block} onSave={onSave} onCancel={onCancel} />;
    case "table":
      return <TableEditor block={block} onSave={onSave} onCancel={onCancel} />;
    default:
      return null;
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/editors/BlockEditor.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/editors/BlockEditor.tsx \
        apps/web/components/snapshot/editors/BlockEditor.test.tsx
git commit -m "feat(web): BlockEditor type dispatcher"
```

---

### Task 6: `BlockToolbar` + `AddBlockMenu` (presentational)

**Files:**
- Create: `apps/web/components/snapshot/BlockToolbar.tsx`, `apps/web/components/snapshot/AddBlockMenu.tsx`
- Test: `apps/web/components/snapshot/blockControls.test.tsx`

**Interfaces:**
- Produces: `BlockToolbar({ onEdit, onDelete, onMoveUp, onMoveDown, canMoveUp, canMoveDown })`; `AddBlockMenu({ onInsert }: { onInsert: (type: BlockType) => void })` — a `+` that opens a picker of the five types and calls `onInsert(type)`.
- Consumes: `BlockType` (Task 1), `Editing.module.css`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/blockControls.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BlockToolbar } from "./BlockToolbar";
import { AddBlockMenu } from "./AddBlockMenu";

describe("block controls", () => {
  it("BlockToolbar fires handlers and disables move at edges", async () => {
    const onDelete = vi.fn();
    const onMoveUp = vi.fn();
    render(
      <BlockToolbar
        onEdit={vi.fn()}
        onDelete={onDelete}
        onMoveUp={onMoveUp}
        onMoveDown={vi.fn()}
        canMoveUp={false}
        canMoveDown={true}
      />,
    );
    expect(screen.getByRole("button", { name: "Move block up" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Delete block" }));
    expect(onDelete).toHaveBeenCalled();
  });

  it("AddBlockMenu opens the picker and reports the chosen type", async () => {
    const onInsert = vi.fn();
    render(<AddBlockMenu onInsert={onInsert} />);
    await userEvent.click(screen.getByRole("button", { name: "Add block" }));
    await userEvent.click(screen.getByRole("button", { name: "Add table block" }));
    expect(onInsert).toHaveBeenCalledWith("table");
  });
});
```

Note: if `toBeDisabled` is unavailable without jest-dom, assert `(screen.getByRole("button", { name: "Move block up" }) as HTMLButtonElement).disabled === true` instead.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/blockControls.test.tsx`
Expected: FAIL — components not found.

- [ ] **Step 3: Create `BlockToolbar.tsx`**

```tsx
import styles from "./Editing.module.css";

export function BlockToolbar({
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
}: {
  onEdit: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}) {
  return (
    <div className={styles.toolbar}>
      <button type="button" className={styles.iconBtn} aria-label="Edit block" onClick={onEdit}>
        Edit
      </button>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Move block up"
        onClick={onMoveUp}
        disabled={!canMoveUp}
      >
        ↑
      </button>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Move block down"
        onClick={onMoveDown}
        disabled={!canMoveDown}
      >
        ↓
      </button>
      <button type="button" className={styles.iconBtn} aria-label="Delete block" onClick={onDelete}>
        Delete
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Create `AddBlockMenu.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { BlockType } from "@/lib/packEdit";
import styles from "./Editing.module.css";

const TYPES: BlockType[] = ["prose", "formula", "table", "figure", "list"];

export function AddBlockMenu({ onInsert }: { onInsert: (type: BlockType) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.addBar}>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Add block"
        onClick={() => setOpen((o) => !o)}
      >
        + Add block
      </button>
      {open && (
        <div className={styles.addMenu}>
          {TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={styles.iconBtn}
              aria-label={`Add ${t} block`}
              onClick={() => {
                setOpen(false);
                onInsert(t);
              }}
            >
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/blockControls.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/snapshot/BlockToolbar.tsx \
        apps/web/components/snapshot/AddBlockMenu.tsx \
        apps/web/components/snapshot/blockControls.test.tsx
git commit -m "feat(web): block toolbar + add-block menu"
```

---

### Task 7: Wire it up — `PackReport` client island + `BlockCell` orchestration

**Files:**
- Modify: `apps/web/components/snapshot/BlockCell.tsx` (rewrite), `apps/web/components/snapshot/BlockCell.module.css` (add toolbar reveal)
- Modify: `apps/web/components/snapshot/PackReport.tsx` (rewrite → client island)
- Test: `apps/web/components/snapshot/PackReport.test.tsx` (add interaction tests; keep the existing render assertions)

**Interfaces:**
- Consumes: `packEdit` transforms + `emptyContent` (Task 1); `BlockView` (Task 2); `BlockEditor` (Task 5); `BlockToolbar` + `AddBlockMenu` (Task 6); `updateBlock`/`createBlock`/`deleteBlock` + `PackBlockOut`/`BlockWrite` (Phase 2a + Task 1).
- Produces: an editable `PackReport`. `BlockCell({ block, canMoveUp, canMoveDown, onSaveContent, onDelete, onMoveUp, onMoveDown })` toggles view/edit and renders the toolbar.

- [ ] **Step 1: Write the failing interaction tests**

Add to `apps/web/components/snapshot/PackReport.test.tsx` (keep the file's existing fixture + 4 render tests; add a mock + these tests). First extend the existing `import { describe, expect, it } from "vitest";` line to also import `vi`. Then add these new imports and the mock at the top (after the existing imports):

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, updateBlock: vi.fn(), createBlock: vi.fn(), deleteBlock: vi.fn() };
});
```

Add these tests (the `pack` fixture already exists in the file):

```tsx
describe("PackReport editing", () => {
  it("edits a prose block and calls updateBlock with the new content", async () => {
    (api.updateBlock as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "00000000-0000-0000-0000-0000000000b1",
      type: "prose",
      content: "changed",
    });
    render(<PackReport pack={pack} />);
    // block b1 is the prose block in the fixture's section
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Edit block"]') as HTMLElement);
    const ta = screen.getByLabelText("Prose (Markdown)");
    await userEvent.clear(ta);
    await userEvent.type(ta, "changed");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(api.updateBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
      { content: { type: "prose", content: "changed" } },
    );
  });

  it("deletes a block optimistically via deleteBlock", async () => {
    (api.deleteBlock as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    render(<PackReport pack={pack} />);
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Delete block"]') as HTMLElement);
    expect(api.deleteBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
    );
    expect(
      document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]'),
    ).toBeNull();
  });

  it("inserts a new block via createBlock and renders it", async () => {
    (api.createBlock as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "new-block-id",
      type: "prose",
      content: "",
    });
    render(<PackReport pack={pack} />);
    // use the first Add-block menu in the section
    await userEvent.click(screen.getAllByRole("button", { name: "Add block" })[0]);
    await userEvent.click(screen.getAllByRole("button", { name: "Add prose block" })[0]);
    expect(api.createBlock).toHaveBeenCalled();
  });
});
```

Note: the fixture in this file has a section id `00000000-0000-0000-0000-0000000000a1` and blocks `b1..b6`. Ensure the prose-edit test targets a prose block id (`b1` is prose in the existing fixture). If a different id is prose, adjust the selector to that id.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: FAIL — no Edit/Delete/Add controls in the DOM yet (PackReport is still read-only).

- [ ] **Step 3: Rewrite `BlockCell.tsx`**

```tsx
"use client";

import { useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { BlockView } from "./BlockView";
import { BlockEditor } from "./editors/BlockEditor";
import { BlockToolbar } from "./BlockToolbar";
import styles from "./BlockCell.module.css";

export function BlockCell({
  block,
  canMoveUp,
  canMoveDown,
  onSaveContent,
  onDelete,
  onMoveUp,
  onMoveDown,
}: {
  block: PackBlockOut;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onSaveContent: (content: BlockWrite) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <div className={styles.cell} data-block-id={block.id}>
      {editing ? (
        <BlockEditor
          block={block}
          onSave={(content) => {
            setEditing(false);
            onSaveContent(content);
          }}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <>
          <div className={styles.toolbarSlot}>
            <BlockToolbar
              onEdit={() => setEditing(true)}
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              canMoveUp={canMoveUp}
              canMoveDown={canMoveDown}
            />
          </div>
          <BlockView block={block} />
        </>
      )}
    </div>
  );
}
```

Append to `apps/web/components/snapshot/BlockCell.module.css`:

```css
.toolbarSlot {
  position: absolute;
  top: var(--space-1);
  right: var(--space-1);
  opacity: 0;
  transition: opacity 140ms cubic-bezier(0.2, 0, 0, 1);
}
.cell:hover .toolbarSlot,
.cell:focus-within .toolbarSlot {
  opacity: 1;
}
```

- [ ] **Step 4: Rewrite `PackReport.tsx` as a client island**

```tsx
"use client";

import { Fragment, useState } from "react";
import { createBlock, deleteBlock, updateBlock } from "@gulp/api-client";
import type { PackBlockOut, PackOut } from "@gulp/api-client";
import {
  emptyContent,
  insertBlockAt,
  moveBlock,
  removeBlock,
  replaceBlock,
  type BlockType,
  type BlockWrite,
} from "@/lib/packEdit";
import { BlockCell } from "./BlockCell";
import { AddBlockMenu } from "./AddBlockMenu";
import { Md } from "./Md";
import styles from "./PackReport.module.css";

export function PackReport({ pack: initialPack }: { pack: PackOut }) {
  const [pack, setPack] = useState(initialPack);
  const [error, setError] = useState<string | null>(null);
  const sid = pack.snapshot_id;

  function saveContent(sectionId: string, blockId: string, content: BlockWrite) {
    const prev = pack;
    const edited = { ...content, id: blockId } as PackBlockOut;
    setPack(replaceBlock(pack, sectionId, blockId, edited));
    updateBlock(sid, blockId, { content }).catch(() => {
      setPack(prev);
      setError("Couldn't save your edit — try again.");
    });
  }

  function del(sectionId: string, blockId: string) {
    const prev = pack;
    setPack(removeBlock(pack, sectionId, blockId));
    deleteBlock(sid, blockId).catch(() => {
      setPack(prev);
      setError("Couldn't delete that block — try again.");
    });
  }

  function move(sectionId: string, blockId: string, dir: -1 | 1) {
    const section = pack.sections.find((s) => s.id === sectionId);
    if (!section) return;
    const i = section.blocks.findIndex((b) => b.id === blockId);
    const newIndex = i + dir;
    if (newIndex < 0 || newIndex >= section.blocks.length) return;
    const prev = pack;
    setPack(moveBlock(pack, sectionId, blockId, newIndex));
    updateBlock(sid, blockId, { position: newIndex }).catch(() => {
      setPack(prev);
      setError("Couldn't reorder — try again.");
    });
  }

  function insert(sectionId: string, index: number, type: BlockType) {
    createBlock(sid, sectionId, { content: emptyContent(type), position: index })
      .then((block) => setPack((p) => insertBlockAt(p, sectionId, index, block)))
      .catch(() => setError("Couldn't add a block — try again."));
  }

  return (
    <article className={styles.report}>
      {error && (
        <div className={styles.errorBar} role="alert">
          {error} <button type="button" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

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
          <AddBlockMenu onInsert={(t) => insert(section.id, 0, t)} />
          {section.blocks.map((block, i) => (
            <Fragment key={block.id}>
              <BlockCell
                block={block}
                canMoveUp={i > 0}
                canMoveDown={i < section.blocks.length - 1}
                onSaveContent={(content) => saveContent(section.id, block.id, content)}
                onDelete={() => del(section.id, block.id)}
                onMoveUp={() => move(section.id, block.id, -1)}
                onMoveDown={() => move(section.id, block.id, 1)}
              />
              <AddBlockMenu onInsert={(t) => insert(section.id, i + 1, t)} />
            </Fragment>
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

Append to `apps/web/components/snapshot/PackReport.module.css`:

```css
.errorBar {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-3); margin-bottom: var(--space-4);
  background: var(--state-risk-tint); color: var(--state-risk-on);
  border-radius: var(--radius-md); font-size: 13px;
}
.errorBar button { text-decoration: underline; color: inherit; }
```

- [ ] **Step 5: Run the full web suite to verify tests pass**

Run: `pnpm --filter @gulp/web exec vitest run`
Expected: PASS — the new editing tests + the existing render tests + all Task 1–6 tests. If the existing render tests reference the removed local `BlockView`/`Md`, they don't (they render `PackReport`), so they stay green.

- [ ] **Step 6: Typecheck**

Run: `pnpm --filter @gulp/web exec tsc --noEmit`
Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/snapshot/BlockCell.tsx \
        apps/web/components/snapshot/BlockCell.module.css \
        apps/web/components/snapshot/PackReport.tsx \
        apps/web/components/snapshot/PackReport.module.css \
        apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): editable pack reader — client island wiring edit/delete/move/insert"
```

---

## Self-Review

**Spec coverage (Phase 2b slice):**
- Per-type editors (prose/formula/table/figure/list) → Tasks 3–5. ✔
- `BlockCell` view/edit toggle + `BlockToolbar` (edit/delete/move) → Tasks 6–7. ✔
- `AddBlockMenu` (`+` insert with type picker) → Tasks 6–7. ✔
- `PackReport` client island holding state, optimistic edit/delete/move + rollback + error banner; insert awaits server → Task 7. ✔
- Reorder = move up/down (via `updateBlock({position})`); drag-and-drop deferred → Global Constraints + Task 7. ✔ (intentional)
- Pure, testable state transforms → Task 1. ✔
- "Re-run wipes edits" confirm → **dropped** (no reachable trigger in the current `ready`-state UI; documented in Global Constraints). ✔ (intentional)

**Placeholder scan:** every code step shows full component/test code and exact commands. The `toHaveValue`/`toBeDisabled` matchers have an explicit no-jest-dom fallback noted inline, so no step depends on an uninstalled matcher.

**Type consistency:** editors all share `({ block: Extract<PackBlockOut,{type:...}>, onSave: (content: BlockWrite) => void, onCancel })`; `BlockEditor` widens `block` to `PackBlockOut` and dispatches. `BlockWrite`/`BlockType` are defined once in `lib/packEdit.ts` and imported everywhere. `PackReport` handlers pass `{ content }` / `{ position }` shapes matching `BlockUpdateBody`, and `createBlock(..., { content, position })` matches `BlockCreateBody`. `BlockCell` props produced in Task 7 match what `PackReport` passes. The api-client helper names (`updateBlock`/`createBlock`/`deleteBlock`) are exactly Phase 2a's exports.

## Manual verification (after execution)

Automated tests can't confirm the composed look/feel. After the branch is green, run `just dev`, open a `ready` snapshot, and confirm: hover reveals the toolbar; Edit swaps a block to its editor and Save persists (survives refresh); ↑/↓ reorder persists; Delete removes and persists; `+ Add block → <type>` inserts a fresh editable block; a forced network failure surfaces the error banner and rolls back.
