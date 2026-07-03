# arXiv paper figures → attachable to the paper report

**Date:** 2026-07-03
**Status:** Design approved, pending spec review
**Branch:** `feat/arxiv-figures`

## 1. Context & problem

When a paper-type knowledge pack is built from an arXiv PDF URL (e.g.
`https://arxiv.org/pdf/2606.17162`), the pack's figure blocks are **text-only**
today: the LLM emits a `FigureBlock` with `label` + `explanation` (a written
description), and nothing renders a real image. The pipeline never sees the
paper's actual figures.

We want to fetch the paper's real figure images from its LaTeX source and let the
user attach any of them to a figure block in the block-editable pack reader, so
the paper report can show the actual figures.

Two facts about the current system shape this design:

- **Figure blocks are text-only** (`services/worker/app/pipeline/schemas.py`
  `FigureBlock`, `services/api/app/schemas/pack.py` `FigureBlockOut`/`FigureWrite`,
  `apps/web/components/snapshot/BlockView.tsx` figure branch).
- **There is no media/binary storage anywhere** — only `settings.export_dir` for
  zip exports. This feature introduces the first binary-asset storage concern.

## 2. Goals / non-goals

**Goals (v1):**

- For a snapshot whose `origin_url` is an arXiv URL, automatically (best-effort)
  download the paper's LaTeX source, extract its figures, convert PDF figures to
  PNG, and store them as a per-snapshot figure gallery.
- In the block editor, browse that gallery and attach a chosen image to a figure
  block; the reader then renders the real image (label/explanation become the
  caption).
- Never let figure extraction affect the correctness or status of the main pack:
  it runs after the pack is `ready` and any failure is swallowed with a log.

**Non-goals (v1):**

- Auto-matching figures to figure blocks (manual pick only).
- EPS and pure-vector (TikZ/PGF, no image file) figures.
- Object storage / CDN / multi-instance file sharing (local filesystem only).
- Signed URLs / per-asset authz (auth is a stub today; see §9).
- Bundling figures into the pack export archive (future; see §11).

## 3. Decisions (locked during brainstorming)

| Question | Decision |
|---|---|
| Attach UX | **Manual gallery pick** — pipeline downloads all figures into a per-snapshot gallery; user attaches one to a figure block in the editor. |
| Image storage | **Local filesystem + API static serving**, mirroring `export_dir`. |
| Non-web formats | **Raster (PNG/JPG/GIF/WebP) pass-through + PDF→PNG via PyMuPDF.** EPS/vector skipped. |
| Trigger | **Automatic during processing**, best-effort, after the pack is `ready`. |
| Extraction strategy | **Hybrid (C):** `\includegraphics`-driven ordering/caption/filter, with a file-scan fallback. |

## 4. Architecture & data flow

```
process_source (services/worker/app/pipeline/run.py)
  set processing → normdoc → digest → persist_pack → status=ready → COMMIT   (unchanged)
  └─ if is_arxiv(origin_url):
       try:  await extract_arxiv_figures(db, source, fetch)   # best-effort, own try/except + own commit
       except: logger.exception(...)   # pack already ready; never rethrow

extract_arxiv_figures:
  eprint_url = arxiv_eprint_url(origin_url)
  tar_bytes  = await fetch(eprint_url)            # reuse injected fetch (testable)
  figures    = extract_figures(tar_bytes)         # pure: bytes → [ExtractedFigure]  (strategy C)
  persist_figures(db, source, figures)            # write files + insert SourceFigure rows, COMMIT
```

The extraction runs **after** the pack is committed as `ready`, in its own
`try/except`, so a failure (arXiv withheld source, weird tarball, convert error)
leaves a fully-working pack with an empty gallery.

## 5. Component design

### 5.1 `services/shared/gulp_shared` (shared: written by worker, read by API)

- **`models/source_figure.py`** — new `SourceFigure` ORM model (§6), registered in
  `models/__init__.py`.
- **`media.py`** — the single source of truth for on-disk layout, so worker (write)
  and API (read) agree:
  - `media_root() -> Path` (from `settings.media_dir`)
  - `figure_relpath(source_id, figure_id, ext) -> str` → `"<source_id>/<figure_id>.<ext>"`
  - `figure_abspath(source_id, figure_id, ext) -> Path`
- **`settings.py`** — add `media_dir: str = "/tmp/gulp-media"` (mirrors `export_dir`).

### 5.2 `services/worker` (extraction pipeline)

New package `app/pipeline/figures/` with small, individually testable units:

- **`adapters/arxiv.py`** (extend existing) — **robust URL parsing is a
  first-class requirement**: the input is whatever the user forwarded, which is
  `abs` *or* `pdf` and comes in many shapes. Factor one shared core and derive the
  rest from it, so `abs`/`pdf`/e-print all normalize identically:
  - `arxiv_id(url) -> str | None` — the canonical id, the single normalization
    point (refactored out of today's `arxiv_abs_url`, which becomes
    `f"abs/{arxiv_id(url)}"`).
  - `arxiv_eprint_url(url) -> str | None` → `https://arxiv.org/e-print/<id>`
  - `is_arxiv(url) -> bool` → `arxiv_id(url) is not None`

  **Accepted / normalized (all yield the same id):**

  | input | id |
  |---|---|
  | `https://arxiv.org/abs/2606.17162` | `2606.17162` |
  | `https://arxiv.org/pdf/2606.17162` | `2606.17162` |
  | `https://arxiv.org/pdf/2606.17162.pdf` | `2606.17162` |
  | `https://arxiv.org/pdf/2606.17162v2` / `…v2.pdf` | `2606.17162v2` (version kept) |
  | `http://www.arxiv.org/abs/2606.17162` / `export.arxiv.org` | `2606.17162` |
  | `https://arxiv.org/abs/cs/0112017` (old-style, subject class) | `cs/0112017` |
  | `https://arxiv.org/abs/2606.17162v2?foo=1#sec` | `2606.17162v2` |
  | `https://arxiv.org/abs/2606.17162/` (trailing slash) | `2606.17162` |

  **Rejected (→ `None`, no fetch):** non-arXiv hosts; non-paper arXiv paths
  (`/list/…`, `/find/…`, `/pdf/` with no id); garbage strings.

  Normalization rules: host ∈ {`arxiv.org`,`www.arxiv.org`,`export.arxiv.org`}
  (case-insensitive); path `^/(pdf|abs)/<id>`; strip a trailing `.pdf`
  (case-insensitive) and any trailing slash; **preserve** the version suffix
  (`vN`) and old-style `subject-class/NNNNNNN`; query/fragment dropped by
  `urlsplit`. Preserving the version pins e-print to the exact version the user
  read (arXiv serves the latest when the version is absent).
- **`figures/tex.py`** — pure TeX scanning:
  - strip TeX comments (unescaped `%` … EOL)
  - `\graphicspath{{dir/}}` resolution
  - ordered `\includegraphics[...]{path}` extraction
  - within `figure`/`figure*` environments, brace-balanced `\caption{...}` and
    `\label{...}` associated with the enclosing `\includegraphics`
  - returns `[TexRef(path, label, caption, order)]` in document order
- **`figures/tarball.py`** — pure archive handling:
  - guard gzip magic (`1f 8b`), `gzip.decompress`, `tarfile.open(fileobj=…)`
  - **safe iteration**: `getmembers()`, skip non-regular members, reject names that
    escape the root (`..`, absolute); read bytes via `extractfile()`. **Never
    `extractall`.**
  - resolve a `TexRef.path` to a member: exact → with candidate extensions
    (`.pdf .png .jpg .jpeg .gif` — TeX usually omits the extension) → basename match
  - fallback file-scan: collect all image-typed members by extension when no
    `\includegraphics` resolved
- **`figures/convert.py`** — format normalization:
  - raster (png/jpg/jpeg/gif/webp): pass-through, mime by sniff/extension
  - pdf: PyMuPDF renders page 0 to PNG at a capped DPI; also yields width/height
  - unsupported (eps/…): return `None` (skipped)
- **`figures/extract.py`** — orchestration: `extract_figures(tar_bytes) ->
  [ExtractedFigure(bytes, mime, ext, label, caption, order, width?, height?)]`,
  applying limits (§9). Combines tex.py + tarball.py + convert.py (strategy C).
- **`figures/persist.py`** — `persist_figures(db, source, figures)`: idempotent
  (delete existing `SourceFigure` rows + files for the source first, mirroring
  `persist_pack`), write each blob to `media.figure_abspath(...)`, insert rows.
- **`pipeline/run.py`** — call `extract_arxiv_figures` after `status=ready` commit,
  guarded, best-effort.

Add **`pymupdf`** to `services/worker/pyproject.toml` (pure-wheel, no system deps).
`gzip`/`tarfile` are stdlib.

### 5.3 `services/api` (list + serve)

- **`schemas/figures.py`** — `FigureAssetOut(id, label, caption, mime_type, width,
  height)`. The web builds the bytes URL from `snapshot_id`+`figure_id`.
- **`services/figures.py`** — `list_figures(db, snapshot_id)`,
  `get_figure_file(db, snapshot_id, figure_id) -> (Path, mime) | None`.
- **`routers/figures.py`** (thin, reuse `_owned_snapshot` ownership):
  - `GET /snapshots/{snapshot_id}/figures` → `list[FigureAssetOut]`
  - `GET /snapshots/{snapshot_id}/figures/{figure_id}` → `FileResponse(path,
    media_type=mime)`; 404 if row/file missing.
  - register in `routers/__init__.py`.
- **Figure block gains `figure_id`**: add `figure_id: uuid.UUID | None = None` to
  `FigureBlockOut` and `FigureWrite` in `schemas/pack.py`. It persists in
  `PackBlock.data` (JSON) via the existing block-update path — no block migration.
- Run `just gen-client` after schema changes.

### 5.4 `apps/web` (attach + render)

- **`FigureEditor.tsx`** — add a gallery picker: fetch
  `GET /snapshots/{id}/figures`, show thumbnails, selecting sets `figure_id`; a
  "detach" clears it. Keep label/explanation as caption fields. Writes
  `{ type: "figure", label, explanation, figure_id }`.
- **`BlockView.tsx`** figure branch — if `figure_id` is set, render
  `<img src={figuresBytesUrl(snapshotId, figure_id)}>` with label/explanation as
  `<figcaption>`; else the current text-only rendering.
- All types come from the regenerated `@gulp/api-client`; the bytes URL is built
  from the client's configured API base.

## 6. Data model & migration

New table `source_figures` (Alembic migration via `just migrate`):

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `source_id` | uuid FK → `sources.id` `ON DELETE CASCADE`, indexed | gallery is per-snapshot |
| `order_index` | int | document order (file-scan fallback: enumeration order) |
| `label` | text, nullable | e.g. `"Figure 3"` or the TeX `\label`; filename in fallback |
| `caption` | text, nullable | from `\caption{...}` |
| `ext` | text | stored file extension (`png`/`jpg`/`gif`) |
| `mime_type` | text | `image/png`, … |
| `width` | int, nullable | best-effort |
| `height` | int, nullable | best-effort |
| `created_at`/`updated_at` | via `TimestampedBase` | |

The figure block's `figure_id` is a **soft reference** held in `PackBlock.data`
JSON (not a DB FK), consistent with the block model's type-specific `data` dict. A
dangling `figure_id` (asset deleted) is handled gracefully: the API returns 404 and
the reader falls back to the text-only rendering. Re-processing rebuilds both the
pack and the gallery, so they stay consistent for the auto path; manual attaches
happen post-processing and are not disturbed unless the user re-processes.

## 7. Storage layout & serving

- On disk: `media_dir/<source_id>/<figure_id>.<ext>`.
- Worker writes; API reads via the shared `gulp_shared.media` helpers — one layout
  definition, no drift.
- Serving: `FileResponse` with the row's `mime_type`. With the current auth stub an
  `<img src>` can hit the endpoint directly.

## 8. Extraction strategy detail (hybrid C)

1. Parse TeX for ordered `\includegraphics` refs + captions/labels (tex.py).
2. Resolve each ref to a tar member; convert per format (convert.py).
3. Keep only successfully-normalized images, in document order, carrying
   caption/label.
4. **Fallback:** if step 1 yielded no resolvable refs, file-scan all image members
   by extension (unordered, filename as label) so best-effort never returns empty
   when images exist.

## 9. Error handling, security, limits

- **Best-effort isolation:** extraction runs after `status=ready`; all failures are
  logged, never rethrown. Pack is unaffected.
- **Per-figure isolation:** a single bad/convert-failing image is skipped; others
  proceed.
- **Tar safety:** never `extractall`; read member bytes only; reject `..`/absolute
  member names (path-traversal defense in depth).
- **Limits (constants, tunable):** max download size (~50 MB), max figures (~40),
  max single-image bytes (~10 MB), PDF render DPI cap (~150). Log when a limit
  truncates so an empty/short gallery is explainable, not silent.
- **arXiv-friendly:** one `e-print` request per paper (no crawling), reuse the
  existing `GulpBot/1.0` UA.
- **Text safety:** captions/labels flow through the same un-encodable-char cleaning
  posture as NormDoc before DB write.
- **Auth (future):** the bytes endpoint is currently open because auth is a dev
  stub; when real auth (S0) lands, revisit with cookie auth or signed URLs.

## 10. Testing

- **Pure units:** arxiv.py `arxiv_id`/`arxiv_eprint_url` (the full §5.2 URL matrix
  — abs & pdf, version suffix, `.pdf`, old-style ids, www/export hosts, trailing
  slash, query/fragment, and the reject cases — extending today's `test_arxiv.py`);
  tex.py (TeX string → refs/captions, incl. `graphicspath`, comments, missing
  extensions, subfigure captions); tarball.py (crafted `.tar.gz` bytes → members,
  traversal rejection); convert.py (tiny PDF → PNG, raster pass-through,
  unsupported → None).
- **Pipeline:** `extract_arxiv_figures` with an injected `fetch` returning a crafted
  tarball → asserts rows + files written under a tmp `media_dir`; failure path
  (`fetch` raises) → no rows, pack still `ready`.
- **API:** list + serve (ownership 404, missing-file 404, correct content-type).
- **Web (vitest, classic JSX — `import React`):** gallery pick sets `figure_id`;
  BlockView renders `<img>` when set, text-only when null.

## 11. Implementation slices

1. **Worker + storage:** `SourceFigure` model + migration, `gulp_shared.media`,
   `media_dir` setting, `figures/` package, arXiv URL helpers, wire into
   `process_source`. Ships the gallery data end-to-end (DB + disk) with tests.
2. **API:** `figures` schema/service/router, `figure_id` on the figure block
   contract, `just gen-client`.
3. **Web:** gallery picker in `FigureEditor`, image rendering in `BlockView`.

## 12. Future (explicitly deferred)

- Auto-match figures to figure blocks by label.
- EPS / TikZ handling.
- Include figures in the pack export archive (`services/worker/app/export`).
- Object storage; signed URLs once real auth exists.
- Figure-file cleanup on source hard-delete (soft-delete keeps files today).
