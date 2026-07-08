# Figure Auto-Link on Import + Insert-Figure-Below-Any-Block Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an offline-generated report is uploaded, auto-link its `figure` blocks to extracted arXiv figures with pure code (no LLM); and let the user insert a pre-linked figure block below any block from a toolbar gallery.

**Architecture:** A new worker module `app/pipeline/figures/match.py` matches "Figure N" block labels to the Nth *logical* figure (subfigure runs collapsed) in TeX-source order; a best-effort post-import hook in the `import_result` arq task extracts figures if missing (arXiv e-print fetch — network only, no LLM) and runs the matcher. On the web side, `PackReport` fetches the figure gallery once and each block's toolbar gains an `InsertFigureMenu` that creates a figure block (label/caption/figure_id pre-filled) below the block via the existing `createBlock` API.

**Tech Stack:** Python 3.13 + SQLAlchemy + pytest (worker); React + TypeScript + vitest/@testing-library (web). No schema/API/DB migrations needed — `FigureBlock.figure_id` and all endpoints already exist.

## Global Constraints

- Auto-link must be **conservative**: never overwrite a non-null `figure_id`; skip entirely when figures came from the file-scan fallback (all rows have `label IS NULL AND caption IS NULL` — their order is filename-sorted, not document order).
- Auto-link is **best-effort**: any failure logs and rolls back but must not change the imported pack's `ready` status (mirror `_maybe_extract_figures` in `services/worker/app/pipeline/run.py:86-92`).
- Auto-link runs **only in the import path** (`import_result` task), not in `process_source`. Out of scope: backfill button, multi-image attachments, LLM-pipeline linking.
- `PackBlock.data` is a JSON column — always assign a **new dict** (`block.data = {**block.data, ...}`), never mutate in place (SQLAlchemy won't detect in-place mutation).
- Soft delete: pack block queries must filter `PackBlock.deleted_at.is_(None)` (base model has `deleted_at`, see `services/shared/gulp_shared/db/base.py:26`).
- Worker tests run from repo root: `uv run pytest services/worker/tests/<file> -v`. Web tests: `pnpm --filter @gulp/web exec vitest run components/snapshot/<file>`.
- Frontend reuses existing CSS classes in `apps/web/components/snapshot/Editing.module.css` (`.toolbar`, `.iconBtn`, `.figureGallery`) — no new CSS.
- Commit after every task. End commit messages with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Matching core — `figures/match.py`

**Files:**
- Create: `services/worker/app/pipeline/figures/match.py`
- Test: `services/worker/tests/test_figures_match.py`

**Interfaces:**
- Consumes: `SourceFigure` (`gulp_shared.models.source_figure`), `KnowledgePack`/`PackSection`/`PackBlock`/`PackBlockType` (`gulp_shared.models.knowledge_pack`).
- Produces (used by Task 2):
  - `fig_number(label: str) -> int | None`
  - `group_logical(figures: list[SourceFigure]) -> list[SourceFigure]`
  - `link_figures(db: Session, source: Source) -> int` — fills `figure_id` on unlinked figure blocks, flushes (does NOT commit), returns number of blocks linked.

- [ ] **Step 1: Write the failing tests**

Create `services/worker/tests/test_figures_match.py`:

```python
# services/worker/tests/test_figures_match.py
import gulp_shared.models  # noqa: F401
from app.pipeline.figures.match import fig_number, group_logical, link_figures
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf,
                  origin_url="https://arxiv.org/abs/2606.17162")
    s.add(snap)
    s.flush()
    return snap


def _figure(s, snap, order, label=None, caption=None):  # type: ignore[no-untyped-def]
    row = SourceFigure(source_id=snap.id, order_index=order, label=label,
                       caption=caption, ext="png", mime_type="image/png")
    s.add(row)
    s.flush()
    return row


def _figure_blocks(s, snap, labels, preset=None):  # type: ignore[no-untyped-def]
    """Pack with one section holding a figure block per label. `preset` maps
    block index -> pre-existing figure_id."""
    pack = KnowledgePack(snapshot_id=snap.id, title="T", key_insight="k",
                         core_contributions=[], references=[], status=PackStatus.ready)
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    s.add(sec)
    s.flush()
    blocks = []
    for i, label in enumerate(labels):
        data = {"label": label, "explanation": "e",
                "figure_id": (preset or {}).get(i)}
        b = PackBlock(section_id=sec.id, block_type=PackBlockType.figure,
                      data=data, position=i)
        s.add(b)
        blocks.append(b)
    s.flush()
    return blocks


def test_fig_number_parses_common_label_shapes() -> None:
    assert fig_number("Figure 3") == 3
    assert fig_number("Fig. 12: overview") == 12
    assert fig_number("figure 2 — attention maps") == 2
    assert fig_number("FIGURE 4") == 4
    assert fig_number("Table 1") is None
    assert fig_number("Architecture") is None
    assert fig_number("") is None


def test_group_logical_collapses_subfigure_runs() -> None:
    def fig(order, label, caption):  # type: ignore[no-untyped-def]
        return SourceFigure(order_index=order, label=label, caption=caption,
                            ext="png", mime_type="image/png")

    rows = [
        fig(0, "fig:a", "First."),
        fig(1, "fig:a", "First."),   # subfigure of the same env
        fig(2, "fig:b", "Second."),
        fig(3, None, None),           # captionless env is its own figure
        fig(4, None, None),           # ...and so is the next one
    ]
    logical = group_logical(rows)
    assert [f.order_index for f in logical] == [0, 2, 3, 4]


def test_group_logical_returns_empty_for_fallback_scan() -> None:
    rows = [
        SourceFigure(order_index=i, label=None, caption=None,
                     ext="png", mime_type="image/png")
        for i in range(3)
    ]
    assert group_logical(rows) == []


def test_link_figures_links_by_number() -> None:
    s = _session()
    snap = _snap(s)
    f1 = _figure(s, snap, 0, label="fig:a", caption="First.")
    f2 = _figure(s, snap, 1, label="fig:b", caption="Second.")
    b_two, b_one = _figure_blocks(s, snap, ["Figure 2", "Figure 1"])
    assert link_figures(s, snap) == 2
    assert b_two.data["figure_id"] == str(f2.id)
    assert b_one.data["figure_id"] == str(f1.id)


def test_link_figures_counts_subfigure_group_as_one() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, label="fig:a", caption="Same.")
    _figure(s, snap, 1, label="fig:a", caption="Same.")
    other = _figure(s, snap, 2, label="fig:b", caption="Other.")
    (block,) = _figure_blocks(s, snap, ["Figure 2"])
    assert link_figures(s, snap) == 1
    assert block.data["figure_id"] == str(other.id)


def test_link_figures_skips_fallback_figures() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0)  # no label, no caption
    (block,) = _figure_blocks(s, snap, ["Figure 1"])
    assert link_figures(s, snap) == 0
    assert block.data["figure_id"] is None


def test_link_figures_never_overwrites_existing_link() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, caption="First.")
    (block,) = _figure_blocks(s, snap, ["Figure 1"], preset={0: "manually-chosen"})
    assert link_figures(s, snap) == 0
    assert block.data["figure_id"] == "manually-chosen"


def test_link_figures_skips_out_of_range_and_unparseable() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, caption="Only one.")
    b_nine, b_none = _figure_blocks(s, snap, ["Figure 9", "Overview diagram"])
    assert link_figures(s, snap) == 0
    assert b_nine.data["figure_id"] is None
    assert b_none.data["figure_id"] is None


def test_link_figures_without_figures_or_pack_is_zero() -> None:
    s = _session()
    snap = _snap(s)
    assert link_figures(s, snap) == 0  # no figures at all
    _figure(s, snap, 0, caption="C.")
    assert link_figures(s, snap) == 0  # figures but no pack
```

- [ ] **Step 2: Run tests to verify they fail**

Run (repo root): `uv run pytest services/worker/tests/test_figures_match.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.figures.match'`

- [ ] **Step 3: Write the implementation**

Create `services/worker/app/pipeline/figures/match.py`:

```python
# services/worker/app/pipeline/figures/match.py
"""Match imported figure blocks ("Figure 3") to extracted SourceFigure rows.

Pure-code matching, no LLM: LaTeX assigns figure numbers in order of figure
environments in the source, so the Nth logical figure in TeX order is
"Figure N". Conservative by design — fallback-scanned figures (no TeX
metadata at all) are skipped because their order is filename-sorted, and an
existing figure_id (a manual link) is never overwritten.
"""

import re

from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
)
from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session

_FIG_NUM = re.compile(r"^fig(?:ure)?\.?\s*(\d+)", re.IGNORECASE)


def fig_number(label: str) -> int | None:
    """'Figure 3' / 'Fig. 12: overview' -> 3 / 12; anything else -> None."""
    m = _FIG_NUM.match(label.strip())
    return int(m.group(1)) if m else None


def group_logical(figures: list[SourceFigure]) -> list[SourceFigure]:
    """Collapse subfigure runs into one representative row per logical figure.

    Rows arrive in order_index order. Consecutive rows sharing the same
    (label, caption) — with at least one of the two set — are subfigures of
    one figure environment; the first row represents the group. Returns []
    when no row has any TeX metadata (file-scan fallback).
    """
    if all(f.label is None and f.caption is None for f in figures):
        return []
    logical: list[SourceFigure] = []
    prev_key: tuple[str | None, str | None] | None = None
    for f in figures:
        key = (f.label, f.caption)
        if key != prev_key or key == (None, None):
            logical.append(f)
        prev_key = key
    return logical


def link_figures(db: Session, source: Source) -> int:
    """Fill figure_id on unlinked figure blocks by figure number.

    Flushes but does not commit. Returns the number of blocks linked.
    """
    figures = list(db.scalars(
        select(SourceFigure)
        .where(SourceFigure.source_id == source.id)
        .order_by(SourceFigure.order_index)
    ))
    logical = group_logical(figures) if figures else []
    if not logical:
        return 0
    blocks = db.scalars(
        select(PackBlock)
        .join(PackSection, PackBlock.section_id == PackSection.id)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            KnowledgePack.snapshot_id == source.id,
            PackBlock.block_type == PackBlockType.figure,
            PackBlock.deleted_at.is_(None),
        )
    )
    linked = 0
    for block in blocks:
        if block.data.get("figure_id"):
            continue  # a manual link wins
        n = fig_number(block.data.get("label") or "")
        if n is None or not 1 <= n <= len(logical):
            continue
        block.data = {**block.data, "figure_id": str(logical[n - 1].id)}
        linked += 1
    db.flush()
    return linked
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/worker/tests/test_figures_match.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/figures/match.py services/worker/tests/test_figures_match.py
git commit -m "feat(worker): match figure blocks to extracted figures by number

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Post-import hook — extract if missing, then link

**Files:**
- Modify: `services/worker/app/pipeline/figures/run.py` (add `link_imported_figures`)
- Modify: `services/worker/app/tasks/__init__.py:60-71` (call it from `import_result`)
- Test: `services/worker/tests/test_figures_link.py`

**Interfaces:**
- Consumes (from Task 1): `link_figures(db, source) -> int`. Existing: `extract_arxiv_figures(db, source, fetch)` (`app/pipeline/figures/run.py:18`), `FetchedDoc`/`fetch_document` (`app/pipeline/adapters/fetch.py`).
- Produces: `async link_imported_figures(db: Session, source: Source, fetch: FetchFn) -> None` in `app.pipeline.figures.run` — extracts figures when the source has none (arXiv only; non-arXiv is a silent no-op inside `extract_arxiv_figures`), then links and commits if anything was linked.

- [ ] **Step 1: Write the failing tests**

Create `services/worker/tests/test_figures_link.py`:

```python
# services/worker/tests/test_figures_link.py
"""Post-import auto-link: extract figures if missing, then match to blocks."""
import gzip
import io
import tarfile

import gulp_shared.models  # noqa: F401
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.run import link_imported_figures
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"
_TEX = (b"\\begin{figure}\\includegraphics{a.png}"
        b"\\caption{Overview.}\\label{fig:o}\\end{figure}")


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s, url="https://arxiv.org/abs/2606.17162"):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf,
                  origin_url=url)
    s.add(snap)
    s.flush()
    return snap


def _pack_with_figure_block(s, snap):  # type: ignore[no-untyped-def]
    pack = KnowledgePack(snapshot_id=snap.id, title="T", key_insight="k",
                         core_contributions=[], references=[], status=PackStatus.ready)
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    s.add(sec)
    s.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.figure,
                      data={"label": "Figure 1", "explanation": "e", "figure_id": None},
                      position=0)
    s.add(block)
    s.flush()
    return block


def _targz(files):  # type: ignore[no-untyped-def]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


async def test_extracts_then_links(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    block = _pack_with_figure_block(s, snap)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        return FetchedDoc(content=_targz({"m.tex": _TEX, "a.png": _PNG}),
                          content_type="application/gzip")

    await link_imported_figures(s, snap, fetch)
    fig = s.scalar(select(SourceFigure).where(SourceFigure.source_id == snap.id))
    assert fig is not None
    assert block.data["figure_id"] == str(fig.id)


async def test_skips_fetch_when_figures_exist(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    block = _pack_with_figure_block(s, snap)
    fig = SourceFigure(source_id=snap.id, order_index=0, label="fig:o",
                       caption="Overview.", ext="png", mime_type="image/png")
    s.add(fig)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch when figures already exist")

    await link_imported_figures(s, snap, fetch)
    assert block.data["figure_id"] == str(fig.id)


async def test_non_arxiv_is_noop(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, url="https://example.com/paper")
    block = _pack_with_figure_block(s, snap)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch non-arxiv sources")

    await link_imported_figures(s, snap, fetch)
    assert block.data["figure_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest services/worker/tests/test_figures_link.py -v`
Expected: FAIL — `ImportError: cannot import name 'link_imported_figures'`

- [ ] **Step 3: Add `link_imported_figures` to `figures/run.py`**

In `services/worker/app/pipeline/figures/run.py`, extend the imports and append the function:

```python
# services/worker/app/pipeline/figures/run.py
"""Best-effort arXiv figure extraction step (spec §4). Callable in isolation with
an injected fetch; the pipeline provides the real one."""

from collections.abc import Awaitable, Callable

from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.adapters.arxiv import arxiv_eprint_url, is_arxiv
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.extract import extract_figures
from app.pipeline.figures.match import link_figures
from app.pipeline.figures.persist import persist_figures

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


async def extract_arxiv_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    url = source.origin_url or ""
    if not is_arxiv(url):
        return
    eprint = arxiv_eprint_url(url)
    if eprint is None:
        return
    doc = await fetch(eprint)
    figures = extract_figures(doc.content)
    if figures:
        persist_figures(db, source, figures)
        db.commit()


async def link_imported_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    """Post-import step: make sure figures exist (arXiv fetch — no LLM), then
    auto-link the pack's figure blocks to them by figure number."""
    have = db.scalar(
        select(SourceFigure.id).where(SourceFigure.source_id == source.id)
    )
    if have is None:
        await extract_arxiv_figures(db, source, fetch)
    if link_figures(db, source):
        db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/worker/tests/test_figures_link.py -v`
Expected: 3 PASS

- [ ] **Step 5: Hook into the `import_result` task**

In `services/worker/app/tasks/__init__.py`:

Extend the imports at the top:

```python
from gulp_shared.models.source import SnapshotStatus, Source
from sqlalchemy.orm import Session

from app.pipeline.adapters.fetch import fetch_document
from app.pipeline.figures.run import link_imported_figures
```

(keep the existing `from gulp_shared.models.source import Source` line's other usages — just widen it to also import `SnapshotStatus`.)

Replace the `import_result` function body and add the helper:

```python
async def import_result(ctx: dict[str, Any], snapshot_id: str, upload_path: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("import_result: snapshot %s not found", snapshot_id)
            return
        with open(upload_path, "rb") as f:
            data = f.read()
        run_import_result(db, source, data)
        if source.status is SnapshotStatus.ready:
            await _maybe_link_figures(db, source)
    finally:
        db.close()


async def _maybe_link_figures(db: Session, source: Source) -> None:
    """Best-effort: the pack is already `ready`; a figure failure must not change that."""
    try:
        await link_imported_figures(db, source, fetch_document)
    except Exception:
        db.rollback()
        logger.exception("figure auto-link failed for %s", source.id)
```

- [ ] **Step 6: Run the full worker suite**

Run: `uv run pytest services/worker/tests -q`
Expected: all pass (existing `test_tasks.py` / `test_export_jobs.py` untouched; note-sources have no `origin_url` matching arXiv, so the new hook is a no-op for them).

- [ ] **Step 7: Commit**

```bash
git add services/worker/app/pipeline/figures/run.py services/worker/app/tasks/__init__.py services/worker/tests/test_figures_link.py
git commit -m "feat(worker): auto-link figures to report blocks after result import

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `InsertFigureMenu` component

**Files:**
- Create: `apps/web/components/snapshot/InsertFigureMenu.tsx`
- Test: `apps/web/components/snapshot/InsertFigureMenu.test.tsx`

**Interfaces:**
- Consumes: `figureUrl(snapshotId, figureId)` and type `FigureAssetOut` from `@gulp/api-client`; CSS classes `.toolbar`, `.iconBtn`, `.figureGallery` from `Editing.module.css`.
- Produces (used by Task 4): `<InsertFigureMenu snapshotId figures onPick />` — renders `null` when `figures` is empty; a 🖼 toggle button (aria-label "Insert figure below") opens a gallery; clicking a thumbnail calls `onPick(figure)` and closes.

- [ ] **Step 1: Write the failing test**

Create `apps/web/components/snapshot/InsertFigureMenu.test.tsx`:

```tsx
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { FigureAssetOut } from "@gulp/api-client";
import { InsertFigureMenu } from "./InsertFigureMenu";

vi.mock("@gulp/api-client", () => ({
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

afterEach(cleanup);

const figs: FigureAssetOut[] = [
  { id: "f1", label: "Figure 1", caption: "c", mime_type: "image/png", width: 4, height: 4 },
];

describe("InsertFigureMenu", () => {
  it("renders nothing when there are no figures", () => {
    const { container } = render(
      <InsertFigureMenu snapshotId="s" figures={[]} onPick={() => {}} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("opens the gallery and picks a figure", () => {
    const onPick = vi.fn();
    render(<InsertFigureMenu snapshotId="s" figures={figs} onPick={onPick} />);
    expect(screen.queryByRole("button", { name: "Figure 1" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /insert figure below/i }));
    fireEvent.click(screen.getByRole("button", { name: "Figure 1" }));
    expect(onPick).toHaveBeenCalledWith(figs[0]);
    expect(screen.queryByRole("button", { name: "Figure 1" })).toBeNull(); // closed
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/InsertFigureMenu.test.tsx`
Expected: FAIL — cannot resolve `./InsertFigureMenu`

- [ ] **Step 3: Write the component**

Create `apps/web/components/snapshot/InsertFigureMenu.tsx`:

```tsx
"use client";

import React, { useState } from "react";
import { figureUrl, type FigureAssetOut } from "@gulp/api-client";
import styles from "./Editing.module.css";

/** Toolbar affordance: pick an extracted paper figure to insert as a new,
 *  already-linked figure block below the current block. */
export function InsertFigureMenu({
  snapshotId,
  figures,
  onPick,
}: {
  snapshotId: string;
  figures: FigureAssetOut[];
  onPick: (figure: FigureAssetOut) => void;
}) {
  const [open, setOpen] = useState(false);
  if (figures.length === 0) return null;
  return (
    <span className={styles.toolbar}>
      <button
        type="button"
        className={styles.iconBtn}
        aria-label="Insert figure below"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        🖼
      </button>
      {open && (
        <span className={styles.figureGallery}>
          {figures.map((f) => (
            <button
              type="button"
              key={f.id}
              aria-label={f.label ?? "figure"}
              onClick={() => {
                setOpen(false);
                onPick(f);
              }}
            >
              <img src={figureUrl(snapshotId, f.id)} alt={f.label ?? ""} />
            </button>
          ))}
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/InsertFigureMenu.test.tsx`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/snapshot/InsertFigureMenu.tsx apps/web/components/snapshot/InsertFigureMenu.test.tsx
git commit -m "feat(web): figure-gallery insert menu component

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Wire the menu into every block's toolbar

**Files:**
- Modify: `apps/web/components/snapshot/PackReport.tsx`
- Modify: `apps/web/components/snapshot/BlockCell.tsx`
- Test: `apps/web/components/snapshot/PackReport.test.tsx` (extend)

**Interfaces:**
- Consumes (from Task 3): `InsertFigureMenu`. Existing: `getFigures`, `createBlock`, `insertBlockAt`, `BlockWrite`.
- Produces: `PackReport` fetches the gallery once on mount; `BlockCell` gains required props `figures: FigureAssetOut[]` and `onInsertFigure: (f: FigureAssetOut) => void`.

- [ ] **Step 1: Extend the PackReport test**

In `apps/web/components/snapshot/PackReport.test.tsx`, add `getFigures: vi.fn(async () => [])` to the `vi.mock` factory's returned object (next to the other mocked functions):

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
    getFigures: vi.fn(async () => []),
  };
});
```

Then add this test inside the existing `describe("PackReport", ...)`:

```tsx
  it("inserts a pre-linked figure block below the chosen block", async () => {
    vi.mocked(api.getFigures).mockResolvedValue([
      { id: "fig-9", label: "Figure 2", caption: "Attention heads.", mime_type: "image/png", width: 8, height: 8 },
    ]);
    vi.mocked(api.createBlock).mockResolvedValue({
      id: "00000000-0000-0000-0000-0000000000c1",
      type: "figure",
      label: "Figure 2",
      explanation: "Attention heads.",
      figure_id: "fig-9",
    });
    render(<PackReport pack={pack} />);
    const menus = await screen.findAllByRole("button", { name: /insert figure below/i });
    await userEvent.click(menus[0]);
    await userEvent.click(screen.getByRole("button", { name: "Figure 2" }));
    expect(api.createBlock).toHaveBeenCalledWith(
      pack.snapshot_id,
      pack.sections[0].id,
      {
        content: { type: "figure", label: "Figure 2", explanation: "Attention heads.", figure_id: "fig-9" },
        position: 1,
      },
    );
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot/PackReport.test.tsx`
Expected: the new test FAILS (no "Insert figure below" buttons found); existing tests still pass.

- [ ] **Step 3: Wire `PackReport.tsx`**

Apply these edits to `apps/web/components/snapshot/PackReport.tsx`:

1. Update imports (add `useEffect`, `getFigures`, `FigureAssetOut`):

```tsx
import React, { Fragment, useEffect, useState } from "react";
import { createBlock, deleteBlock, getFigures, updateBlock } from "@gulp/api-client";
import type { FigureAssetOut, PackBlockOut, PackOut } from "@gulp/api-client";
```

2. Inside the component, after the `sid` line, add the one-shot gallery fetch (same UUID guard as `FigureEditor.tsx:10,30`):

```tsx
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
```

(put the regex at module scope, above `export function PackReport`), and in the component:

```tsx
  const [figures, setFigures] = useState<FigureAssetOut[]>([]);

  useEffect(() => {
    // Only fetch for a real snapshot id — a malformed id would 422 the API.
    if (!UUID_RE.test(sid)) return;
    let alive = true;
    getFigures(sid)
      .then((figs) => alive && setFigures(figs))
      .catch(() => alive && setFigures([]));
    return () => {
      alive = false;
    };
  }, [sid]);
```

3. Add the insert handler next to the existing `insert`:

```tsx
  function insertFigure(sectionId: string, index: number, f: FigureAssetOut) {
    setError(null);
    const content: BlockWrite = {
      type: "figure",
      label: f.label ?? "Figure",
      explanation: f.caption ?? "",
      figure_id: f.id,
    };
    createBlock(sid, sectionId, { content, position: index })
      .then((block) => setPack((p) => insertBlockAt(p, sectionId, index, block)))
      .catch(() => setError("Couldn't add the figure — try again."));
  }
```

4. Pass the new props to `BlockCell` (inside the `section.blocks.map((block, i) => ...)`):

```tsx
                <BlockCell
                  snapshotId={sid}
                  block={block}
                  canMoveUp={i > 0}
                  canMoveDown={i < section.blocks.length - 1}
                  figures={figures}
                  onInsertFigure={(f) => insertFigure(section.id, i + 1, f)}
                  onSaveContent={(content) => saveContent(section.id, block.id, content)}
                  onDelete={() => del(section.id, block.id)}
                  onMoveUp={() => move(section.id, block.id, -1)}
                  onMoveDown={() => move(section.id, block.id, 1)}
                  onDiscuss={() => setSelectedBlockId(block.id)}
                />
```

- [ ] **Step 4: Wire `BlockCell.tsx`**

Apply these edits to `apps/web/components/snapshot/BlockCell.tsx`:

1. Imports:

```tsx
import type { FigureAssetOut, PackBlockOut } from "@gulp/api-client";
import { InsertFigureMenu } from "./InsertFigureMenu";
```

2. Add the two props to the signature (after `canMoveDown`):

```tsx
  figures,
  onInsertFigure,
```

and to the type:

```tsx
  figures: FigureAssetOut[];
  onInsertFigure: (figure: FigureAssetOut) => void;
```

3. Render the menu next to the toolbar, inside the `toolbarSlot` div:

```tsx
          <div className={styles.toolbarSlot}>
            <BlockToolbar
              onEdit={() => setEditing(true)}
              onDelete={onDelete}
              onMoveUp={onMoveUp}
              onMoveDown={onMoveDown}
              onDiscuss={onDiscuss}
              canMoveUp={canMoveUp}
              canMoveDown={canMoveDown}
            />
            <InsertFigureMenu snapshotId={snapshotId} figures={figures} onPick={onInsertFigure} />
          </div>
```

- [ ] **Step 5: Run the web test suites**

Run: `pnpm --filter @gulp/web exec vitest run components/snapshot`
Expected: all pass, including the new PackReport test. If other tests render `BlockCell` directly, add the two new props there (`figures={[]}` `onInsertFigure={() => {}}`).

- [ ] **Step 6: Type-check and full test**

Run: `pnpm --filter @gulp/web exec tsc --noEmit && pnpm --filter @gulp/web test`
Expected: no type errors, all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/snapshot/PackReport.tsx apps/web/components/snapshot/BlockCell.tsx apps/web/components/snapshot/PackReport.test.tsx
git commit -m "feat(web): insert a pre-linked figure block below any block

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Final verification

- [ ] `uv run pytest services/worker/tests -q` — worker suite green
- [ ] `pnpm --filter @gulp/web test` — web suite green
- [ ] `just test` (if the environment supports it) — whole-repo gate
