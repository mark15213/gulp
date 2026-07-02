# Block-Editable Pack Reader — Phase 3b: Per-Block Chat UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-side per-block chat panel — click `💬` on a block to open a slide-over `ChatPanel` that loads the block's conversation and posts grounded questions — driving Phase 3a's `getBlockMessages`/`postBlockMessage`.

**Architecture:** A `ChatPanel` client component (fixed right-side slide-over) loads history on open and sends questions (optimistic user bubble + appended assistant reply, with a "thinking" state). `BlockToolbar` gains a `💬` button; `BlockCell` forwards an `onDiscuss` callback; `PackReport` holds `selectedBlockId` state and renders the panel as an overlay for the selected block. Uses the design tokens; reuses `@/components/ui/Button` for Send.

**Tech Stack:** Next.js client components + CSS Modules + `@gulp/ui` tokens + `@gulp/api-client` (Phase 3a helpers); Vitest + @testing-library/react.

## Global Constraints

- **Depends on Phase 3a:** `getBlockMessages(snapshotId, blockId): Promise<MessageOut[]>`, `postBlockMessage(snapshotId, blockId, { content }): Promise<MessageOut>`, `MessageOut { id, role, content, created_at }` (all in `@gulp/api-client`).
- **Web talks to the backend only through `@gulp/api-client`** — no hand-written fetch types.
- **Tokens/primitives from `@gulp/ui`**; CSS Modules only, NO Tailwind, no local token redefinition; reuse `@/components/ui/Button`. No white/raw-hex — user bubbles use `--blue-50`/`--blue-700`, assistant uses `--fill`/`--text-1`.
- **No `@testing-library/jest-dom`** — native assertions only; every multi-render test file has `afterEach(cleanup)` (vitest here has no auto-cleanup). New TSX needs `import React` (classic-JSX). Gate every task on `pnpm --filter @gulp/web exec tsc --noEmit` (exit 0) in addition to vitest.
- **Layout (v1):** `ChatPanel` is a fixed right-side slide-over overlay at all widths (the snapshot page is 960px, too narrow to dock a 380px rail beside the 720px reader without cramping). A wide-screen docked three-pane is a documented follow-up.
- English only. Copy never blames the user (`docs/03 §2.7`).

**Environment:**
- Web tests: `pnpm --filter @gulp/web exec vitest run <path>`. Stage only each task's files; leave the pre-existing WIP (services/*) untouched.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `apps/web/components/snapshot/ChatPanel.tsx` (+ `.module.css`) | slide-over chat for one block | create |
| `apps/web/components/snapshot/ChatPanel.test.tsx` | ChatPanel behavior | create |
| `apps/web/components/snapshot/BlockToolbar.tsx` | add `💬` (Discuss) button | modify |
| `apps/web/components/snapshot/BlockCell.tsx` | forward `onDiscuss` | modify |
| `apps/web/components/snapshot/PackReport.tsx` | `selectedBlockId` state + render overlay panel | modify |
| `apps/web/components/snapshot/PackReport.test.tsx` | `💬` opens panel test | modify |

---

### Task 1: `ChatPanel` component

**Files:**
- Create: `apps/web/components/snapshot/ChatPanel.tsx`, `apps/web/components/snapshot/ChatPanel.module.css`
- Test: `apps/web/components/snapshot/ChatPanel.test.tsx`

**Interfaces:**
- Produces: `ChatPanel({ snapshotId, blockId, onClose }: { snapshotId: string; blockId: string; onClose: () => void })` — loads history via `getBlockMessages` on mount/`blockId` change; `Send` posts via `postBlockMessage` (optimistic user bubble + appended assistant reply; "thinking" while awaiting; rollback + error on failure); a close (`✕`) button calls `onClose`.
- Consumes: `getBlockMessages`, `postBlockMessage`, `MessageOut` (`@gulp/api-client`); `@/components/ui/Button`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/ChatPanel.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "@gulp/api-client";
import { ChatPanel } from "./ChatPanel";

vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return { ...actual, getBlockMessages: vi.fn(), postBlockMessage: vi.fn() };
});

afterEach(cleanup);

const getMock = () => api.getBlockMessages as ReturnType<typeof vi.fn>;
const postMock = () => api.postBlockMessage as ReturnType<typeof vi.fn>;

describe("ChatPanel", () => {
  it("loads and renders the block's conversation on open", async () => {
    getMock().mockResolvedValue([
      { id: "m1", role: "user", content: "Why masking?", created_at: "" },
      { id: "m2", role: "assistant", content: "Because bidirectionality.", created_at: "" },
    ]);
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={vi.fn()} />);
    expect(await screen.findByText("Because bidirectionality.")).toBeTruthy();
    expect(screen.getByText("Why masking?")).toBeTruthy();
    expect(getMock()).toHaveBeenCalledWith("s1", "b1");
  });

  it("sends a question and appends the assistant reply", async () => {
    getMock().mockResolvedValue([]);
    postMock().mockResolvedValue({ id: "a1", role: "assistant", content: "Grounded answer.", created_at: "" });
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={vi.fn()} />);
    const input = await screen.findByLabelText("Ask about this block");
    await userEvent.type(input, "What is it?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(postMock()).toHaveBeenCalledWith("s1", "b1", { content: "What is it?" });
    expect(await screen.findByText("Grounded answer.")).toBeTruthy();
    expect(screen.getByText("What is it?")).toBeTruthy(); // optimistic user bubble stays
  });

  it("close button calls onClose", async () => {
    getMock().mockResolvedValue([]);
    const onClose = vi.fn();
    render(<ChatPanel snapshotId="s1" blockId="b1" onClose={onClose} />);
    await userEvent.click(await screen.findByLabelText("Close chat"));
    expect(onClose).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/ChatPanel.test.tsx`
Expected: FAIL — `Cannot find module './ChatPanel'`.

- [ ] **Step 3: Create `ChatPanel.tsx`**

```tsx
"use client";

import React, { useEffect, useState } from "react";
import { getBlockMessages, postBlockMessage, type MessageOut } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";
import styles from "./ChatPanel.module.css";

export function ChatPanel({
  snapshotId,
  blockId,
  onClose,
}: {
  snapshotId: string;
  blockId: string;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setMessages([]);
    setError(null);
    getBlockMessages(snapshotId, blockId)
      .then((m) => {
        if (active) setMessages(m);
      })
      .catch(() => {
        if (active) setError("Couldn't load the conversation.");
      });
    return () => {
      active = false;
    };
  }, [snapshotId, blockId]);

  async function send() {
    const q = draft.trim();
    if (!q || sending) return;
    setError(null);
    setSending(true);
    setDraft("");
    const optimistic: MessageOut = { id: `tmp-${q}`, role: "user", content: q, created_at: "" };
    setMessages((m) => [...m, optimistic]);
    try {
      const answer = await postBlockMessage(snapshotId, blockId, { content: q });
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
    <aside className={styles.panel} aria-label="Block chat">
      <div className={styles.header}>
        <span className="t-label">Discuss</span>
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
      <div className={styles.composer}>
        <textarea
          aria-label="Ask about this block"
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

- [ ] **Step 4: Create `ChatPanel.module.css`**

```css
/* Slide-over chat for one block (docs/03: right panel, hairline, tokens only). */
.panel {
  position: fixed;
  top: 0;
  right: 0;
  height: 100vh;
  width: 380px;
  background: var(--surface);
  border-left: 1px solid var(--border);
  box-shadow: var(--shadow-overlay);
  display: flex;
  flex-direction: column;
  z-index: 50;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
}
.close {
  color: var(--text-2);
  font-size: 15px;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.user {
  align-self: flex-end;
  background: var(--blue-50);
  color: var(--blue-700);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  max-width: 85%;
}
.assistant {
  align-self: flex-start;
  background: var(--fill);
  color: var(--text-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  max-width: 85%;
  white-space: pre-wrap;
}
.thinking {
  align-self: flex-start;
  color: var(--text-2);
  font-size: 13px;
}
.err {
  padding: var(--space-2) var(--space-4);
  background: var(--state-risk-tint);
  color: var(--state-risk-on);
  font-size: 13px;
}
.composer {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border);
}
.input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-2);
  font: inherit;
  resize: none;
  min-height: 40px;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/ChatPanel.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Typecheck + commit**

Run: `pnpm --filter @gulp/web exec tsc --noEmit` (exit 0), then:

```bash
git add apps/web/components/snapshot/ChatPanel.tsx \
        apps/web/components/snapshot/ChatPanel.module.css \
        apps/web/components/snapshot/ChatPanel.test.tsx
git commit -m "feat(web): per-block ChatPanel (load history, send grounded question)"
```

---

### Task 2: Wire `💬` into the toolbar, cell, and PackReport

**Files:**
- Modify: `apps/web/components/snapshot/BlockToolbar.tsx`, `apps/web/components/snapshot/BlockCell.tsx`, `apps/web/components/snapshot/PackReport.tsx`
- Test: `apps/web/components/snapshot/PackReport.test.tsx`

**Interfaces:**
- Consumes: `ChatPanel` (Task 1).
- Produces: `BlockToolbar` gains `onDiscuss: () => void` (a `💬` button, aria-label "Discuss block"); `BlockCell` gains `onDiscuss: () => void` (forwarded to the toolbar); `PackReport` holds `selectedBlockId` state, passes `onDiscuss={() => setSelectedBlockId(block.id)}` to each cell, and renders `<ChatPanel snapshotId={sid} blockId={selectedBlockId} onClose={() => setSelectedBlockId(null)} />` when set.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/components/snapshot/PackReport.test.tsx`. First extend the existing `vi.mock("@gulp/api-client", ...)` return object to also stub the chat helpers — change it to:

```tsx
vi.mock("@gulp/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@gulp/api-client")>();
  return {
    ...actual,
    updateBlock: vi.fn(),
    createBlock: vi.fn(),
    deleteBlock: vi.fn(),
    getBlockMessages: vi.fn(),
    postBlockMessage: vi.fn(),
  };
});
```

Then add this test (the `pack` fixture already exists; `b1` is the prose block):

```tsx
describe("PackReport chat", () => {
  it("opens the ChatPanel for a block when its Discuss button is clicked", async () => {
    (api.getBlockMessages as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<PackReport pack={pack} />);
    const cell = document.querySelector('[data-block-id="00000000-0000-0000-0000-0000000000b1"]')!;
    await userEvent.click(cell.querySelector('[aria-label="Discuss block"]') as HTMLElement);
    // the panel mounts and loads this block's messages
    expect(await screen.findByLabelText("Ask about this block")).toBeTruthy();
    expect(api.getBlockMessages).toHaveBeenCalledWith(
      pack.snapshot_id,
      "00000000-0000-0000-0000-0000000000b1",
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: FAIL — no "Discuss block" button exists yet.

- [ ] **Step 3: Add `💬` to `BlockToolbar.tsx`**

Add `onDiscuss: () => void` to the prop type and a button (place it before Delete):

```tsx
export function BlockToolbar({
  onEdit,
  onDelete,
  onMoveUp,
  onMoveDown,
  onDiscuss,
  canMoveUp,
  canMoveDown,
}: {
  onEdit: () => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDiscuss: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}) {
```

and, inside the `<div className={styles.toolbar}>`, add before the Delete button:

```tsx
      <button type="button" className={styles.iconBtn} aria-label="Discuss block" onClick={onDiscuss}>
        💬
      </button>
```

- [ ] **Step 4: Forward `onDiscuss` through `BlockCell.tsx`**

Add `onDiscuss: () => void` to `BlockCell`'s prop type and pass it to `BlockToolbar`:

```tsx
export function BlockCell({
  block,
  canMoveUp,
  canMoveDown,
  onSaveContent,
  onDelete,
  onMoveUp,
  onMoveDown,
  onDiscuss,
}: {
  block: PackBlockOut;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onSaveContent: (content: BlockWrite) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onDiscuss: () => void;
}) {
```

and in the `<BlockToolbar ... />` usage add the prop:

```tsx
            <BlockToolbar
              onEdit={() => setEditing(true)}
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              onDiscuss={onDiscuss}
              canMoveUp={canMoveUp}
              canMoveDown={canMoveDown}
            />
```

- [ ] **Step 5: Add `selectedBlockId` + the panel to `PackReport.tsx`**

Add the import:

```tsx
import { ChatPanel } from "./ChatPanel";
```

Add state (next to the existing `error` state):

```tsx
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
```

Pass `onDiscuss` to each `BlockCell` (add the prop to the existing usage):

```tsx
                onDiscuss={() => setSelectedBlockId(block.id)}
```

Wrap the return in a fragment and render the panel after the `</article>`:

```tsx
  return (
    <>
      <article className={styles.report}>
        {/* ...unchanged article body... */}
      </article>
      {selectedBlockId && (
        <ChatPanel
          key={selectedBlockId}
          snapshotId={sid}
          blockId={selectedBlockId}
          onClose={() => setSelectedBlockId(null)}
        />
      )}
    </>
  );
```

(Keep the entire existing `<article>` body exactly as-is — only wrap it in the fragment and append the `ChatPanel`.) The `key={selectedBlockId}` is load-bearing: it remounts `ChatPanel` when the selected block changes, so a send still in flight from a previous block can't bleed its reply into the newly-selected block's state.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm --filter @gulp/web exec vitest run`
Expected: PASS — the new chat-open test + all existing PackReport tests (the extra `💬` button doesn't affect the render assertions) + the ChatPanel tests.

- [ ] **Step 7: Typecheck + commit**

Run: `pnpm --filter @gulp/web exec tsc --noEmit` (exit 0), then:

```bash
git add apps/web/components/snapshot/BlockToolbar.tsx \
        apps/web/components/snapshot/BlockCell.tsx \
        apps/web/components/snapshot/PackReport.tsx \
        apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): wire per-block Discuss (💬) to open the ChatPanel"
```

---

## Self-Review

**Spec coverage (Phase 3 frontend slice):**
- `ChatPanel` loads history + sends grounded questions with a thinking state → Task 1. ✔
- `💬` on the toolbar opens the panel for that block; `PackReport` holds `selectedBlockId`; panel closes → Tasks 1–2. ✔
- Right-side panel → Task 1 CSS (fixed slide-over overlay; docked-on-wide deferred, documented). ✔
- Tokens-only, native tests + `afterEach(cleanup)`, tsc gate → all tasks. ✔
- Persisted history is shown (reload on open) — the backend persists both turns; the panel reloads on each open. ✔

**Placeholder scan:** full code + commands in every step; no TBD.

**Type consistency:** `ChatPanel({snapshotId, blockId, onClose})` (Task 1) is exactly what `PackReport` renders (Task 2). `onDiscuss: () => void` added consistently to `BlockToolbar` and `BlockCell` and supplied by `PackReport`. `MessageOut`/`getBlockMessages`/`postBlockMessage` are the Phase 3a exports. The extended `vi.mock` adds `getBlockMessages`/`postBlockMessage` so the existing interaction tests still resolve.

## Deferred (documented, non-blocking)
- Wide-screen **docked** three-pane (reader + panel side-by-side) — v1 is a fixed overlay because the 960px snapshot page can't dock a 380px rail beside a 720px reader without cramping. A later pass can widen the pack view and dock on `≥1280px`, overlay below.
- Streaming answers (SSE), markdown rendering of assistant messages (currently plain text), and per-message timestamps — all v1-deferred.

## Manual verification (after execution)
`just up && just dev`, open a `ready` snapshot, hover a block → `💬` → panel opens on the right → ask a question → grounded answer appears (needs a real `anthropic_api_key`, or observe the request); reopen the panel → history persists; `✕` closes it.
