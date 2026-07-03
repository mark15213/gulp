# arXiv Paper Figures — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For arXiv paper snapshots, fetch the LaTeX source, extract figures (PDF→PNG), store them on the filesystem, and let the block editor attach a real figure image to a figure block.

**Architecture:** A best-effort worker step runs *after* the pack is `ready`: derive the arXiv `e-print` URL → download the source tarball → extract figures (hybrid `\includegraphics` + file-scan) → normalize (PDF→PNG via PyMuPDF) → write files under `media_dir/<source_id>/<figure_id>.<ext>` + insert `source_figures` rows. The API lists/serves figures; the web attaches one to a figure block via a new `figure_id` soft reference stored in the block's JSON `data`.

**Tech Stack:** Python 3.13, SQLAlchemy, FastAPI, Alembic, PyMuPDF (`pymupdf`), stdlib `gzip`/`tarfile`; Next.js + `@gulp/api-client` (openapi-fetch); pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-07-03-arxiv-figures-design.md`

## Global Constraints

- **English only** in code, comments, commits (repo rule 6). UI copy may be bilingual.
- **Data model is the contract:** Python `gulp_shared` is source of truth; TS consumes generated `@gulp/api-client`. After API schema changes run `just gen-client`. Never hand-write TS types that duplicate it.
- **Layering:** API routers thin → `app/services` → `gulp_shared`. Worker persistence uses `gulp_shared` models.
- **Capture never blocks on AI:** figure extraction is worker-side, after the pack is `ready`, best-effort (failures logged, never rethrown, never change pack status).
- **Per-package pytest:** run `cd services/<pkg> && uv run pytest` (repo-root pytest collides on the api/worker `app` namespace).
- **Worktree:** work happens in `feat/arxiv-figures` (already created). Run `pnpm install` once before web tests if `node_modules` is absent.
- **Lint stays green:** run `just lint` before finishing a slice (ruff zero, mypy per-service, eslint).
- **Limits (constants):** max tarball 50 MiB, max figures 40, max single image 10 MiB, PDF render 150 DPI.
- **arXiv-friendly:** reuse the existing `GulpBot/1.0` UA; one `e-print` request per paper (no crawling).

---

## Slice 1 — Worker + storage

### Task 1: `SourceFigure` model, `media_dir` setting, media path helpers

**Files:**
- Create: `services/shared/gulp_shared/models/source_figure.py`
- Modify: `services/shared/gulp_shared/models/__init__.py`
- Modify: `services/shared/gulp_shared/settings.py:16` (add `media_dir`)
- Create: `services/shared/gulp_shared/media.py`
- Test: `services/shared/tests/test_source_figure.py`

**Interfaces:**
- Produces: `SourceFigure` ORM (`id, source_id, order_index, label, caption, ext, mime_type, width, height` + timestamps); `media.media_root() -> Path`, `media.figure_relpath(source_id, figure_id, ext) -> str`, `media.figure_abspath(source_id, figure_id, ext) -> Path`.

- [ ] **Step 1: Write the failing test**

```python
# services/shared/tests/test_source_figure.py
import uuid

import gulp_shared.models  # noqa: F401  (register all tables)
from gulp_shared.db import Base
from gulp_shared.media import figure_abspath, figure_relpath, media_root
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_source_figure_row_roundtrips() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    s.add(snap)
    s.flush()
    fig = SourceFigure(source_id=snap.id, order_index=0, label="Figure 1",
                       caption="A cat.", ext="png", mime_type="image/png",
                       width=640, height=480)
    s.add(fig)
    s.commit()
    got = s.scalar(select(SourceFigure).where(SourceFigure.source_id == snap.id))
    assert got is not None and got.label == "Figure 1" and got.ext == "png"


def test_media_path_helpers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", "/data/media")
    sid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    fid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    assert figure_relpath(sid, fid, "png") == f"{sid}/{fid}.png"
    assert figure_abspath(sid, fid, "png") == media_root() / str(sid) / f"{fid}.png"
```

- [ ] **Step 2: Run it — expect failure** — `cd services/shared && uv run pytest tests/test_source_figure.py -v` → ImportError (`source_figure`/`media` missing).

- [ ] **Step 3: Implement the model**

```python
# services/shared/gulp_shared/models/source_figure.py
"""SourceFigure — one extracted paper figure, scoped to a Source (arXiv figures feature)."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SourceFigure(TimestampedBase, Base):
    __tablename__ = "source_figures"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str | None] = mapped_column(Text, default=None)
    caption: Mapped[str | None] = mapped_column(Text, default=None)
    ext: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
```

- [ ] **Step 4: Register the model** — in `services/shared/gulp_shared/models/__init__.py` add `from gulp_shared.models.source_figure import SourceFigure` and add `"SourceFigure"` to `__all__`.

- [ ] **Step 5: Add the setting** — in `services/shared/gulp_shared/settings.py`, after `export_dir`:

```python
    media_dir: str = "/tmp/gulp-media"
```

- [ ] **Step 6: Implement the media helpers**

```python
# services/shared/gulp_shared/media.py
"""On-disk layout for stored media (paper figures). Worker writes; API reads.
One definition so the two never disagree: media_dir/<source_id>/<figure_id>.<ext>."""

import uuid
from pathlib import Path

from gulp_shared.settings import settings


def media_root() -> Path:
    return Path(settings.media_dir)


def figure_relpath(source_id: uuid.UUID, figure_id: uuid.UUID, ext: str) -> str:
    return f"{source_id}/{figure_id}.{ext}"


def figure_abspath(source_id: uuid.UUID, figure_id: uuid.UUID, ext: str) -> Path:
    return media_root() / str(source_id) / f"{figure_id}.{ext}"
```

- [ ] **Step 7: Run tests — expect PASS** — `cd services/shared && uv run pytest tests/test_source_figure.py -v`.

- [ ] **Step 8: Commit**

```bash
git add services/shared/gulp_shared/models/source_figure.py services/shared/gulp_shared/models/__init__.py services/shared/gulp_shared/settings.py services/shared/gulp_shared/media.py services/shared/tests/test_source_figure.py
git commit -m "feat(shared): SourceFigure model + media_dir path helpers"
```

---

### Task 2: Alembic migration for `source_figures`

**Files:**
- Create: `services/api/alembic/versions/a7b8c9d0e1f2_source_figures.py`

**Interfaces:**
- Consumes: `SourceFigure` model (Task 1). Produces: the `source_figures` table on Postgres.

- [ ] **Step 1: Confirm the current head**

Run: `cd services/api && uv run --package gulp-api alembic heads`
Expected: a single head `f6a7b8c9d0e1 (head)`. If it differs, use that value as `down_revision` below.

- [ ] **Step 2: Write the migration** (hand-written; mirrors existing idioms — `sa.Uuid()`, `sa.DateTime(timezone=True)`, `op.f(...)` index names)

```python
# services/api/alembic/versions/a7b8c9d0e1f2_source_figures.py
"""source_figures: extracted paper figures scoped to a source

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
import sqlalchemy as sa
from alembic import op

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'source_figures',
        sa.Column('source_id', sa.Uuid(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('ext', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_source_figures_source_id'), 'source_figures', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_source_figures_source_id'), table_name='source_figures')
    op.drop_table('source_figures')
```

- [ ] **Step 3: Apply and verify** (requires local infra)

Run: `just up && just migrate-up`
Expected: `Running upgrade f6a7b8c9d0e1 -> a7b8c9d0e1f2, source_figures ...`
If Docker/Postgres is unavailable in this environment, at minimum verify the file chains: `cd services/api && uv run --package gulp-api alembic history | head` shows `a7b8c9d0e1f2` above `f6a7b8c9d0e1`.

- [ ] **Step 4: Commit**

```bash
git add services/api/alembic/versions/a7b8c9d0e1f2_source_figures.py
git commit -m "feat(api): migration for source_figures table"
```

---

### Task 3: Robust arXiv URL helpers

**Files:**
- Modify: `services/worker/app/pipeline/adapters/arxiv.py`
- Test: `services/worker/tests/test_arxiv.py` (extend)

**Interfaces:**
- Produces: `arxiv_id(url) -> str | None`, `arxiv_eprint_url(url) -> str | None`, `is_arxiv(url) -> bool`. `arxiv_abs_url` keeps its current behavior, now derived from `arxiv_id`.

- [ ] **Step 1: Write failing tests** (append to `services/worker/tests/test_arxiv.py`)

```python
from app.pipeline.adapters.arxiv import arxiv_eprint_url, arxiv_id, is_arxiv


def test_arxiv_id_normalizes_all_forms() -> None:
    cases = {
        "https://arxiv.org/abs/2606.17162": "2606.17162",
        "https://arxiv.org/pdf/2606.17162": "2606.17162",
        "https://arxiv.org/pdf/2606.17162.pdf": "2606.17162",
        "https://arxiv.org/pdf/2606.17162v2": "2606.17162v2",
        "https://arxiv.org/pdf/2606.17162v2.pdf": "2606.17162v2",
        "http://www.arxiv.org/abs/2606.17162": "2606.17162",
        "https://export.arxiv.org/pdf/2606.17162": "2606.17162",
        "https://arxiv.org/abs/cs/0112017": "cs/0112017",
        "https://arxiv.org/abs/2606.17162v2?foo=1#s": "2606.17162v2",
        "https://arxiv.org/abs/2606.17162/": "2606.17162",
    }
    for url, want in cases.items():
        assert arxiv_id(url) == want, url


def test_arxiv_id_rejects_non_papers() -> None:
    assert arxiv_id("https://example.com/pdf/x") is None
    assert arxiv_id("https://arxiv.org/list/cs.CL/recent") is None
    assert arxiv_id("https://arxiv.org/pdf/") is None
    assert arxiv_id("not a url") is None


def test_arxiv_eprint_url_and_is_arxiv() -> None:
    assert arxiv_eprint_url("https://arxiv.org/pdf/2606.17162v2") == "https://arxiv.org/e-print/2606.17162v2"
    assert arxiv_eprint_url("https://example.com/x") is None
    assert is_arxiv("https://arxiv.org/abs/2606.17162") is True
    assert is_arxiv("https://example.com/x") is False
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_arxiv.py -v` → ImportError.

- [ ] **Step 3: Refactor `arxiv.py`** — replace the id/abs logic so one core normalizes; keep `arxiv_title` unchanged.

```python
def arxiv_id(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in _ARXIV_HOSTS:
        return None
    path = parts.path.rstrip("/")           # tolerate a trailing slash
    m = _ARXIV_PATH.match(path)
    if not m:
        return None
    ident = m.group(1)
    return ident or None


def arxiv_abs_url(url: str) -> str | None:
    ident = arxiv_id(url)
    return f"https://arxiv.org/abs/{ident}" if ident else None


def arxiv_eprint_url(url: str) -> str | None:
    ident = arxiv_id(url)
    return f"https://arxiv.org/e-print/{ident}" if ident else None


def is_arxiv(url: str) -> bool:
    return arxiv_id(url) is not None
```

Also make the `.pdf` strip case-insensitive: change `_ARXIV_PATH` to
`re.compile(r"^/(?:pdf|abs)/(.+?)(?:\.pdf)?$", re.IGNORECASE)`.

- [ ] **Step 4: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_arxiv.py -v` (all, incl. the pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/adapters/arxiv.py services/worker/tests/test_arxiv.py
git commit -m "feat(worker): robust arxiv_id/eprint URL helpers (abs & pdf, versions, old-style)"
```

---

### Task 4: Figure dataclasses + TeX scanning

**Files:**
- Create: `services/worker/app/pipeline/figures/__init__.py` (empty)
- Create: `services/worker/app/pipeline/figures/types.py`
- Create: `services/worker/app/pipeline/figures/tex.py`
- Test: `services/worker/tests/test_figures_tex.py`

**Interfaces:**
- Produces: `TexRef(path, label, caption, order)`, `ExtractedFigure(data, ext, mime, label, caption, order, width, height)`; `parse_graphicspath(tex) -> list[str]`, `parse_tex_refs(tex) -> list[TexRef]` (document order, comments stripped internally).

- [ ] **Step 1: Write failing tests**

```python
# services/worker/tests/test_figures_tex.py
from app.pipeline.figures.tex import parse_graphicspath, parse_tex_refs


def test_ordered_refs_with_caption_and_label() -> None:
    tex = r"""
    \begin{figure}
      \includegraphics[width=1\linewidth]{figures/arch}
      \caption{The architecture.}\label{fig:arch}
    \end{figure}
    Text \includegraphics{plot.png} inline.
    """
    refs = parse_tex_refs(tex)
    assert [r.path for r in refs] == ["figures/arch", "plot.png"]
    assert refs[0].caption == "The architecture." and refs[0].label == "fig:arch"
    assert refs[1].caption is None
    assert [r.order for r in refs] == [0, 1]


def test_comments_are_ignored() -> None:
    tex = "% \\includegraphics{ignored.png}\n\\includegraphics{real.png}\n"
    assert [r.path for r in parse_tex_refs(tex)] == ["real.png"]


def test_graphicspath() -> None:
    assert parse_graphicspath(r"\graphicspath{{figs/}{img/}}") == ["figs/", "img/"]
    assert parse_graphicspath("no graphicspath here") == []
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_tex.py -v`.

- [ ] **Step 3: Implement `types.py`**

```python
# services/worker/app/pipeline/figures/types.py
"""Shared value types for the figure-extraction pipeline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TexRef:
    path: str            # raw \includegraphics target (extension often omitted)
    label: str | None
    caption: str | None
    order: int


@dataclass(frozen=True)
class ExtractedFigure:
    data: bytes
    ext: str             # normalized stored extension: png|jpg|jpeg|gif|webp
    mime: str            # image/png, image/jpeg, ...
    label: str | None
    caption: str | None
    order: int
    width: int | None
    height: int | None
```

- [ ] **Step 4: Implement `tex.py`**

```python
# services/worker/app/pipeline/figures/tex.py
"""Best-effort TeX scanning: ordered \\includegraphics refs + figure captions.

Not a real TeX parser — deliberately small and forgiving. Feeds the hybrid
extractor (spec §8); the tarball file-scan fallback covers whatever this misses.
"""

import re

from app.pipeline.figures.types import TexRef

_COMMENT = re.compile(r"(?<!\\)%.*")
_INCLUDE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
_FIGURE_ENV = re.compile(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", re.DOTALL)
_CAPTION = re.compile(r"\\caption\{([^}]*)\}")
_LABEL = re.compile(r"\\label\{([^}]+)\}")
_GRAPHICSPATH = re.compile(r"\\graphicspath\{((?:\{[^}]*\})+)\}")
_PATH_ITEM = re.compile(r"\{([^}]*)\}")


def _strip_comments(tex: str) -> str:
    return "\n".join(_COMMENT.sub("", line) for line in tex.splitlines())


def parse_graphicspath(tex: str) -> list[str]:
    m = _GRAPHICSPATH.search(_strip_comments(tex))
    return _PATH_ITEM.findall(m.group(1)) if m else []


def parse_tex_refs(tex: str) -> list[TexRef]:
    body = _strip_comments(tex)
    # Map each figure-env includegraphics span to that env's caption/label.
    env_meta: dict[int, tuple[str | None, str | None]] = {}
    for env in _FIGURE_ENV.finditer(body):
        cap = _CAPTION.search(env.group(1))
        lab = _LABEL.search(env.group(1))
        caption = cap.group(1).strip() if cap else None
        label = lab.group(1).strip() if lab else None
        for inc in _INCLUDE.finditer(env.group(1)):
            env_meta[env.start(1) + inc.start()] = (caption, label)

    refs: list[TexRef] = []
    for inc in _INCLUDE.finditer(body):
        caption, label = env_meta.get(inc.start(), (None, None))
        refs.append(TexRef(path=inc.group(1).strip(), label=label,
                           caption=caption, order=len(refs)))
    return refs
```

- [ ] **Step 5: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_tex.py -v`.

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/pipeline/figures/__init__.py services/worker/app/pipeline/figures/types.py services/worker/app/pipeline/figures/tex.py services/worker/tests/test_figures_tex.py
git commit -m "feat(worker): figure dataclasses + best-effort TeX scanning"
```

---

### Task 5: Safe tarball reading + member resolution

**Files:**
- Create: `services/worker/app/pipeline/figures/tarball.py`
- Test: `services/worker/tests/test_figures_tarball.py`

**Interfaces:**
- Consumes: nothing from figures yet. Produces: `TarMember(name, data)`; `read_tar_gz(blob, *, max_total) -> list[TarMember]`; `resolve_member(ref_path, graphicspath, members) -> TarMember | None`.

- [ ] **Step 1: Write failing tests**

```python
# services/worker/tests/test_figures_tarball.py
import gzip
import io
import tarfile

from app.pipeline.figures.tarball import read_tar_gz, resolve_member


def _targz(files: dict[str, bytes], *, unsafe_name: str | None = None) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if unsafe_name:
            info = tarfile.TarInfo(unsafe_name)
            info.size = 3
            tar.addfile(info, io.BytesIO(b"bad"))
    return gzip.compress(raw.getvalue())


def test_reads_members_and_skips_traversal() -> None:
    blob = _targz({"main.tex": b"hi", "fig/a.png": b"PNG"}, unsafe_name="../evil.png")
    members = read_tar_gz(blob, max_total=1_000_000)
    names = {m.name for m in members}
    assert "main.tex" in names and "fig/a.png" in names
    assert "../evil.png" not in names  # path traversal rejected


def test_resolve_by_extension_and_graphicspath() -> None:
    blob = _targz({"figs/arch.pdf": b"%PDF", "plot.png": b"PNG"})
    members = read_tar_gz(blob, max_total=1_000_000)
    # ref omits extension and lives under graphicspath "figs/"
    assert resolve_member("arch", ["figs/"], members).name == "figs/arch.pdf"
    # exact-with-extension
    assert resolve_member("plot.png", [], members).name == "plot.png"
    # basename fallback
    assert resolve_member("sub/arch", [], members).name == "figs/arch.pdf"
    assert resolve_member("missing", [], members) is None
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_tarball.py -v`.

- [ ] **Step 3: Implement `tarball.py`**

```python
# services/worker/app/pipeline/figures/tarball.py
"""Safe read of an arXiv e-print tarball into in-memory members + ref resolution.

Never extractall; never touch the filesystem. Reject members whose names escape
the archive root (path traversal), and cap cumulative bytes."""

import gzip
import io
import posixpath
import tarfile
from dataclasses import dataclass

_CANDIDATE_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".eps")


@dataclass(frozen=True)
class TarMember:
    name: str
    data: bytes


def _is_safe(name: str) -> bool:
    if name.startswith("/") or ".." in name.split("/"):
        return False
    return not posixpath.isabs(name)


def read_tar_gz(blob: bytes, *, max_total: int) -> list[TarMember]:
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    members: list[TarMember] = []
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
            for info in tar.getmembers():
                if not info.isfile() or not _is_safe(info.name):
                    continue
                f = tar.extractfile(info)
                if f is None:
                    continue
                data = f.read()
                total += len(data)
                if total > max_total:
                    break
                members.append(TarMember(name=info.name, data=data))
    except tarfile.TarError:
        return []
    return members


def resolve_member(
    ref_path: str, graphicspath: list[str], members: list[TarMember]
) -> TarMember | None:
    by_name = {m.name: m for m in members}
    prefixes = ["", *graphicspath]
    candidates: list[str] = []
    for prefix in prefixes:
        base = f"{prefix}{ref_path}"
        candidates.append(base)
        if "." not in posixpath.basename(base):
            candidates += [base + ext for ext in _CANDIDATE_EXTS]
    for cand in candidates:
        if cand in by_name:
            return by_name[cand]
    # basename fallback (with/without extension)
    want = posixpath.basename(ref_path)
    for m in members:
        mb = posixpath.basename(m.name)
        if mb == want or mb.rsplit(".", 1)[0] == want:
            return m
    return None
```

- [ ] **Step 4: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_tarball.py -v`.

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/figures/tarball.py services/worker/tests/test_figures_tarball.py
git commit -m "feat(worker): safe e-print tarball reading + figure ref resolution"
```

---

### Task 6: Format normalization (PDF→PNG via PyMuPDF)

**Files:**
- Modify: `services/worker/pyproject.toml` (add `pymupdf`)
- Create: `services/worker/app/pipeline/figures/convert.py`
- Test: `services/worker/tests/test_figures_convert.py`

**Interfaces:**
- Produces: `normalize(name, data) -> tuple[bytes, str, str, int | None, int | None] | None` returning `(data, ext, mime, width, height)`; `None` for unsupported (eps/other).

- [ ] **Step 1: Add the dependency** — in `services/worker/pyproject.toml` `dependencies`, add `"pymupdf>=1.24"`. Then `just setup` (or `cd services/worker && uv sync`).

- [ ] **Step 2: Write failing tests**

```python
# services/worker/tests/test_figures_convert.py
import fitz  # PyMuPDF

from app.pipeline.figures.convert import normalize


def _one_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page(width=120, height=90)
    return doc.tobytes()


def test_raster_passthrough_maps_mime() -> None:
    out = normalize("figs/plot.JPG", b"\xff\xd8\xff\xe0rawjpeg")
    assert out is not None
    data, ext, mime, w, h = out
    assert (ext, mime) == ("jpg", "image/jpeg") and data == b"\xff\xd8\xff\xe0rawjpeg"


def test_pdf_is_rendered_to_png_with_dims() -> None:
    out = normalize("figs/arch.pdf", _one_page_pdf())
    assert out is not None
    data, ext, mime, w, h = out
    assert ext == "png" and mime == "image/png"
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and w and h


def test_unsupported_returns_none() -> None:
    assert normalize("old.eps", b"%!PS") is None
```

- [ ] **Step 3: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_convert.py -v`.

- [ ] **Step 4: Implement `convert.py`**

```python
# services/worker/app/pipeline/figures/convert.py
"""Normalize a figure file to a web-displayable raster (spec §5.2).

Raster (png/jpg/jpeg/gif/webp) passes through; PDF renders page 0 to PNG via
PyMuPDF (pure wheel, no system deps). EPS / vector-only return None (skipped)."""

import fitz  # PyMuPDF

_RASTER_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}
_PDF_DPI = 150


def normalize(name: str, data: bytes) -> tuple[bytes, str, str, int | None, int | None] | None:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in _RASTER_MIME:
        return (data, ext, _RASTER_MIME[ext], None, None)
    if ext == "pdf":
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            if doc.page_count == 0:
                return None
            pix = doc.load_page(0).get_pixmap(dpi=_PDF_DPI)
            return (pix.tobytes("png"), "png", "image/png", pix.width, pix.height)
        except Exception:
            return None
    return None
```

- [ ] **Step 5: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_convert.py -v`.

- [ ] **Step 6: Commit**

```bash
git add services/worker/pyproject.toml services/worker/app/pipeline/figures/convert.py services/worker/tests/test_figures_convert.py
git commit -m "feat(worker): figure format normalization (PDF->PNG via PyMuPDF)"
```

---

### Task 7: Extraction orchestration (hybrid strategy + limits)

**Files:**
- Create: `services/worker/app/pipeline/figures/extract.py`
- Test: `services/worker/tests/test_figures_extract.py`

**Interfaces:**
- Consumes: `read_tar_gz`, `resolve_member` (Task 5); `parse_tex_refs`, `parse_graphicspath` (Task 4); `normalize` (Task 6). Produces: `extract_figures(tar_bytes) -> list[ExtractedFigure]` and the module constants `MAX_FIGURES`, `MAX_TOTAL_BYTES`, `MAX_IMAGE_BYTES`.

- [ ] **Step 1: Write failing tests**

```python
# services/worker/tests/test_figures_extract.py
import gzip
import io
import tarfile

from app.pipeline.figures.extract import extract_figures


def _targz(files: dict[str, bytes]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"


def test_tex_driven_order_and_captions() -> None:
    tex = (r"\begin{figure}\includegraphics{a}\caption{First}\end{figure}"
           r"\includegraphics{b.png}")
    blob = _targz({"main.tex": tex.encode(), "a.png": _PNG, "b.png": _PNG})
    figs = extract_figures(blob)
    assert [f.order for f in figs] == [0, 1]
    assert figs[0].caption == "First" and figs[0].ext == "png"


def test_file_scan_fallback_when_no_tex_refs() -> None:
    blob = _targz({"main.tex": b"no includes here", "z.png": _PNG})
    figs = extract_figures(blob)
    assert len(figs) == 1 and figs[0].ext == "png"


def test_no_images_returns_empty() -> None:
    assert extract_figures(_targz({"main.tex": b"text only"})) == []
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_extract.py -v`.

- [ ] **Step 3: Implement `extract.py`**

```python
# services/worker/app/pipeline/figures/extract.py
"""Hybrid figure extraction (spec §8): TeX-driven order/caption + file-scan fallback."""

import logging
import posixpath

from app.pipeline.figures.convert import normalize
from app.pipeline.figures.tarball import TarMember, read_tar_gz, resolve_member
from app.pipeline.figures.tex import parse_graphicspath, parse_tex_refs
from app.pipeline.figures.types import ExtractedFigure

logger = logging.getLogger("gulp.worker")

MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_FIGURES = 40
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf")


def _tex_source(members: list[TarMember]) -> str:
    parts = [m.data.decode("utf-8", "replace") for m in members if m.name.lower().endswith(".tex")]
    return "\n".join(parts)


def _make(member: TarMember, order: int) -> ExtractedFigure | None:
    if len(member.data) > MAX_IMAGE_BYTES:
        return None
    norm = normalize(member.name, member.data)
    if norm is None:
        return None
    data, ext, mime, w, h = norm
    return ExtractedFigure(data=data, ext=ext, mime=mime, label=None,
                           caption=None, order=order, width=w, height=h)


def extract_figures(tar_bytes: bytes) -> list[ExtractedFigure]:
    members = read_tar_gz(tar_bytes, max_total=MAX_TOTAL_BYTES)
    if not members:
        return []
    tex = _tex_source(members)
    graphicspath = parse_graphicspath(tex)

    figures: list[ExtractedFigure] = []
    used: set[str] = set()
    for ref in parse_tex_refs(tex):
        member = resolve_member(ref.path, graphicspath, members)
        if member is None or member.name in used:
            continue
        fig = _make(member, len(figures))
        if fig is None:
            continue
        used.add(member.name)
        figures.append(ExtractedFigure(**{**fig.__dict__, "label": ref.label, "caption": ref.caption}))
        if len(figures) >= MAX_FIGURES:
            break

    if figures:
        return figures

    # Fallback: file-scan every image-like member (spec §8 step 4), stable order.
    for member in sorted(members, key=lambda m: m.name):
        if not member.name.lower().endswith(_IMAGE_EXTS):
            continue
        fig = _make(member, len(figures))
        if fig is None:
            continue
        figures.append(fig)
        if len(figures) >= MAX_FIGURES:
            break
    if not figures:
        logger.info("extract_figures: no usable figures in tarball")
    return figures
```

- [ ] **Step 4: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_extract.py -v`.

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/figures/extract.py services/worker/tests/test_figures_extract.py
git commit -m "feat(worker): hybrid figure extraction orchestration + limits"
```

---

### Task 8: Persist figures (files + rows, idempotent)

**Files:**
- Create: `services/worker/app/pipeline/figures/persist.py`
- Test: `services/worker/tests/test_figures_persist.py`

**Interfaces:**
- Consumes: `ExtractedFigure` (Task 4), `gulp_shared.media` (Task 1), `SourceFigure` (Task 1). Produces: `persist_figures(db, source, figures) -> list[SourceFigure]` — idempotent (clears the source's prior figure rows + files first).

- [ ] **Step 1: Write failing test**

```python
# services/worker/tests/test_figures_persist.py
import gulp_shared.models  # noqa: F401
from app.pipeline.figures.persist import persist_figures
from app.pipeline.figures.types import ExtractedFigure
from gulp_shared.db import Base
from gulp_shared.media import figure_abspath
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    s.add(snap)
    s.flush()
    return snap


def _fig(order: int) -> ExtractedFigure:
    return ExtractedFigure(data=b"\x89PNG\r\n\x1a\nx", ext="png", mime="image/png",
                           label=f"Figure {order}", caption="c", order=order,
                           width=10, height=10)


def test_persist_writes_files_and_rows(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    rows = persist_figures(s, snap, [_fig(0), _fig(1)])
    s.commit()
    assert len(rows) == 2
    for r in rows:
        assert figure_abspath(snap.id, r.id, r.ext).read_bytes().startswith(b"\x89PNG")
    assert len(list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))) == 2


def test_persist_is_idempotent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    persist_figures(s, snap, [_fig(0), _fig(1)])
    s.commit()
    persist_figures(s, snap, [_fig(0)])  # replace
    s.commit()
    rows = list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))
    assert len(rows) == 1
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_persist.py -v`.

- [ ] **Step 3: Implement `persist.py`**

```python
# services/worker/app/pipeline/figures/persist.py
"""Persist extracted figures: clear the source's prior figures, then write
files + rows. Idempotent, mirroring persist_pack (re-run replaces cleanly)."""

import shutil
import uuid

from gulp_shared.media import figure_abspath, media_root
from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.pipeline.figures.types import ExtractedFigure


def persist_figures(
    db: Session, source: Source, figures: list[ExtractedFigure]
) -> list[SourceFigure]:
    db.execute(delete(SourceFigure).where(SourceFigure.source_id == source.id))
    db.flush()
    shutil.rmtree(media_root() / str(source.id), ignore_errors=True)

    rows: list[SourceFigure] = []
    for fig in figures:
        fig_id = uuid.uuid4()
        path = figure_abspath(source.id, fig_id, fig.ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fig.data)
        row = SourceFigure(
            id=fig_id, source_id=source.id, order_index=fig.order,
            label=fig.label, caption=fig.caption, ext=fig.ext,
            mime_type=fig.mime, width=fig.width, height=fig.height,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows
```

- [ ] **Step 4: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_persist.py -v`.

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/figures/persist.py services/worker/tests/test_figures_persist.py
git commit -m "feat(worker): persist extracted figures to files + source_figures rows"
```

---

### Task 9: Orchestrator + wire into `process_source` (best-effort)

**Files:**
- Create: `services/worker/app/pipeline/figures/run.py`
- Modify: `services/worker/app/pipeline/run.py`
- Test: `services/worker/tests/test_figures_run.py`

**Interfaces:**
- Consumes: `arxiv_eprint_url`, `is_arxiv` (Task 3); `extract_figures` (Task 7); `persist_figures` (Task 8); `FetchFn`/`FetchedDoc` (existing). Produces: `extract_arxiv_figures(db, source, fetch) -> None`. Wires a guarded call into `process_source` after the pack is `ready`.

- [ ] **Step 1: Write failing tests**

```python
# services/worker/tests/test_figures_run.py
import gzip
import io
import tarfile

import gulp_shared.models  # noqa: F401
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.run import extract_arxiv_figures
from gulp_shared.db import Base
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s, url):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf, origin_url=url)
    s.add(snap)
    s.flush()
    return snap


def _targz(files):  # type: ignore[no-untyped-def]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


async def test_extracts_for_arxiv_url(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, "https://arxiv.org/pdf/2606.17162")

    async def fetch(url):  # type: ignore[no-untyped-def]
        assert url == "https://arxiv.org/e-print/2606.17162"
        return FetchedDoc(content=_targz({"m.tex": b"\\includegraphics{a.png}", "a.png": _PNG}),
                          content_type="application/gzip")

    await extract_arxiv_figures(s, snap, fetch)
    assert len(list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))) == 1


async def test_non_arxiv_is_noop(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, "https://example.com/paper.pdf")

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch for non-arxiv")

    await extract_arxiv_figures(s, snap, fetch)
    assert list(s.scalars(select(SourceFigure))) == []
```

- [ ] **Step 2: Run — expect failure** — `cd services/worker && uv run pytest tests/test_figures_run.py -v`.

- [ ] **Step 3: Implement `figures/run.py`**

```python
# services/worker/app/pipeline/figures/run.py
"""Best-effort arXiv figure extraction step (spec §4). Callable in isolation with
an injected fetch; the pipeline provides the real one."""

from collections.abc import Awaitable, Callable

from gulp_shared.models.source import Source
from sqlalchemy.orm import Session

from app.pipeline.adapters.arxiv import arxiv_eprint_url, is_arxiv
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.extract import extract_figures
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
```

- [ ] **Step 4: Wire into `process_source`** — in `services/worker/app/pipeline/run.py`, add the import and a guarded call after the `ready` commit. Replace the end of the `try` block:

```python
        digest = await run_digest(normdoc, provider=provider, config=config)
        persist_pack(db, source, digest)
        source.status = SnapshotStatus.ready
        db.commit()
        await _maybe_extract_figures(db, source, fetch)
```

Add the import near the top (`from app.pipeline.figures.run import extract_arxiv_figures`) and this helper below `process_source`:

```python
async def _maybe_extract_figures(db: Session, source: Source, fetch: FetchFn) -> None:
    """Best-effort: the pack is already `ready`; a figure failure must not change that."""
    try:
        await extract_arxiv_figures(db, source, fetch)
    except Exception:
        db.rollback()
        logger.exception("arxiv figure extraction failed for %s", source.id)
```

- [ ] **Step 5: Add a pipeline guard test** — append to `services/worker/tests/test_figures_run.py`:

```python
async def test_pipeline_swallows_figure_errors(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    from app.pipeline.run import _maybe_extract_figures
    s = _session()
    snap = _snap(s, "https://arxiv.org/pdf/2606.17162")

    async def boom(url):  # type: ignore[no-untyped-def]
        raise RuntimeError("network down")

    await _maybe_extract_figures(s, snap, boom)   # must not raise
    assert snap.status == SnapshotStatus.ready
```

- [ ] **Step 6: Run — expect PASS** — `cd services/worker && uv run pytest tests/test_figures_run.py -v`.

- [ ] **Step 7: Run the full worker suite + lint** — `cd services/worker && uv run pytest -q` then `just lint`.

- [ ] **Step 8: Commit**

```bash
git add services/worker/app/pipeline/figures/run.py services/worker/app/pipeline/run.py services/worker/tests/test_figures_run.py
git commit -m "feat(worker): best-effort arxiv figure extraction wired into process_source"
```

---

## Slice 2 — API

### Task 10: Add `figure_id` to the figure block contract

**Files:**
- Modify: `services/api/app/schemas/pack.py:31-36,63-67`
- Modify: `services/worker/app/pipeline/schemas.py:30-34`
- Test: `services/api/tests/test_pack_mutations.py` (extend)

**Interfaces:**
- Produces: `FigureBlockOut.figure_id: uuid.UUID | None` and `FigureWrite.figure_id: uuid.UUID | None`. The pack service already round-trips arbitrary `data` keys (`block_dict` spreads `b.data`; `update_block` stores `model_dump(exclude={"type"})`) — so no service change is needed.

- [ ] **Step 1: Write failing test** (append to `services/api/tests/test_pack_mutations.py`; reuse that file's existing helpers/fixtures for building a snapshot+pack+figure block — mirror the pattern already there)

```python
def test_update_figure_block_stores_figure_id(db) -> None:  # type: ignore[no-untyped-def]
    from app.services.pack import update_block
    from app.schemas.pack import BlockUpdate
    ids = _figure_block(db)  # helper that adds a figure block; add it mirroring _block in test_pack_router
    out = update_block(db, ids["snap"], ids["block"], BlockUpdate.model_validate(
        {"content": {"type": "figure", "label": "F1", "explanation": "e",
                     "figure_id": str(ids["figure_id"])}}))
    assert str(out["figure_id"]) == str(ids["figure_id"])
```

Add a `_figure_block` helper in the same file (mirrors `_block` in `test_pack_router.py`): create snapshot → pack → section → a `PackBlock(block_type=PackBlockType.figure, data={"label":"F1","explanation":"e"})`, and a `SourceFigure` row on the snapshot; return `{"snap", "block", "figure_id"}`.

- [ ] **Step 2: Run — expect failure** — `cd services/api && uv run pytest tests/test_pack_mutations.py -k figure_id -v` (fails: `figure_id` dropped by the schema).

- [ ] **Step 3: Add the field** — in `services/api/app/schemas/pack.py`, add to both `FigureBlockOut` and `FigureWrite`:

```python
    figure_id: uuid.UUID | None = None
```

And in `services/worker/app/pipeline/schemas.py` `FigureBlock`, add the same (`figure_id: str | None = None`) so the one contract stays mirrored (the LLM leaves it null).

- [ ] **Step 4: Run — expect PASS** — `cd services/api && uv run pytest tests/test_pack_mutations.py -k figure_id -v`, then the full `cd services/api && uv run pytest -q` and `cd services/worker && uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/schemas/pack.py services/worker/app/pipeline/schemas.py services/api/tests/test_pack_mutations.py
git commit -m "feat(api): figure blocks carry an optional figure_id"
```

---

### Task 11: Figures list + serve endpoints

**Files:**
- Create: `services/api/app/schemas/figures.py`
- Create: `services/api/app/services/figures.py`
- Create: `services/api/app/routers/figures.py`
- Modify: `services/api/app/main.py` (import + `include_router`)
- Test: `services/api/tests/test_figures_api.py`

**Interfaces:**
- Consumes: `SourceFigure`, `gulp_shared.media` (Task 1); `_owned_snapshot` pattern (mirror `routers/pack.py`). Produces: `GET /snapshots/{snapshot_id}/figures -> list[FigureAssetOut]`; `GET /snapshots/{snapshot_id}/figures/{figure_id} -> FileResponse`.

- [ ] **Step 1: Write failing tests**

```python
# services/api/tests/test_figures_api.py
import uuid

from app.deps import get_db
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.media import figure_abspath
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID

_PNG = b"\x89PNG\r\n\x1a\nx"


def _client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _snap_with_figure(db, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    fig = SourceFigure(source_id=snap.id, order_index=0, label="F1", caption="c",
                       ext="png", mime_type="image/png", width=1, height=1)
    db.add(fig)
    db.commit()
    p = figure_abspath(snap.id, fig.id, "png")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_PNG)
    return snap.id, fig.id


def test_list_figures(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, fid = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["id"] == str(fid) and body[0]["label"] == "F1"
    app.dependency_overrides.clear()


def test_serve_figure_bytes(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, fid = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures/{fid}")
    assert r.status_code == 200 and r.content == _PNG
    assert r.headers["content-type"].startswith("image/png")
    app.dependency_overrides.clear()


def test_missing_figure_404(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, _ = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures/{uuid.uuid4()}")
    assert r.status_code == 404
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run — expect failure** — `cd services/api && uv run pytest tests/test_figures_api.py -v`.

- [ ] **Step 3: Implement the schema**

```python
# services/api/app/schemas/figures.py
"""Figure gallery contract — becomes the OpenAPI type the web reads."""

import uuid

from pydantic import BaseModel


class FigureAssetOut(BaseModel):
    id: uuid.UUID
    label: str | None
    caption: str | None
    mime_type: str
    width: int | None
    height: int | None
```

- [ ] **Step 4: Implement the service**

```python
# services/api/app/services/figures.py
"""Figure gallery queries + on-disk resolution."""

import uuid
from pathlib import Path

from gulp_shared.media import figure_abspath
from gulp_shared.models.source_figure import SourceFigure
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_figures(db: Session, snapshot_id: uuid.UUID) -> list[SourceFigure]:
    return list(
        db.scalars(
            select(SourceFigure)
            .where(SourceFigure.source_id == snapshot_id, SourceFigure.deleted_at.is_(None))
            .order_by(SourceFigure.order_index)
        )
    )


def figure_file(db: Session, snapshot_id: uuid.UUID, figure_id: uuid.UUID) -> tuple[Path, str] | None:
    fig = db.scalar(
        select(SourceFigure).where(
            SourceFigure.id == figure_id,
            SourceFigure.source_id == snapshot_id,
            SourceFigure.deleted_at.is_(None),
        )
    )
    if fig is None:
        return None
    path = figure_abspath(snapshot_id, figure_id, fig.ext)
    if not path.exists():
        return None
    return path, fig.mime_type
```

- [ ] **Step 5: Implement the router**

```python
# services/api/app/routers/figures.py
"""Figure gallery endpoints — thin (docs/05 D4). Ownership mirrors routers/pack.py."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.figures import FigureAssetOut
from app.services.figures import figure_file, list_figures

router = APIRouter()


def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.get("/snapshots/{snapshot_id}/figures", response_model=list[FigureAssetOut])
def list_figures_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FigureAssetOut]:
    _owned_snapshot(db, snapshot_id, user)
    return [FigureAssetOut.model_validate(f, from_attributes=True) for f in list_figures(db, snapshot_id)]


@router.get("/snapshots/{snapshot_id}/figures/{figure_id}")
def get_figure_route(
    snapshot_id: uuid.UUID,
    figure_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _owned_snapshot(db, snapshot_id, user)
    found = figure_file(db, snapshot_id, figure_id)
    if found is None:
        raise HTTPException(status_code=404, detail="figure not found")
    path, mime = found
    return FileResponse(path, media_type=mime)
```

- [ ] **Step 6: Register the router** — in `services/api/app/main.py`, add `figures` to the routers import and `app.include_router(figures.router, tags=["figures"])`.

- [ ] **Step 7: Run — expect PASS** — `cd services/api && uv run pytest tests/test_figures_api.py -v`, then full `cd services/api && uv run pytest -q` and `just lint`.

- [ ] **Step 8: Regenerate the client** — `just gen-client` (updates `packages/api-client/src/schema.gen.ts` with the new paths + `figure_id`).

- [ ] **Step 9: Commit**

```bash
git add services/api/app/schemas/figures.py services/api/app/services/figures.py services/api/app/routers/figures.py services/api/app/main.py services/api/tests/test_figures_api.py packages/api-client/src/schema.gen.ts
git commit -m "feat(api): list + serve source figures; regenerate api-client"
```

---

## Slice 3 — Web

### Task 12: api-client helpers for figures

**Files:**
- Modify: `packages/api-client/src/index.ts`
- Test: `apps/web/lib/figures.test.ts` (new) — or co-locate a small unit test

**Interfaces:**
- Consumes: generated `paths`, exported `baseUrl`, `client` (Task 11). Produces: `getFigures(snapshotId) -> Promise<FigureAssetOut[]>`, `figureUrl(snapshotId, figureId) -> string`, and type `FigureAssetOut`.

- [ ] **Step 1: Add helpers to `packages/api-client/src/index.ts`**

```typescript
export type FigureAssetOut =
  paths["/snapshots/{snapshot_id}/figures"]["get"]["responses"]["200"]["content"]["application/json"][number];

export async function getFigures(snapshotId: string): Promise<FigureAssetOut[]> {
  const { data, error } = await client.GET("/snapshots/{snapshot_id}/figures", {
    params: { path: { snapshot_id: snapshotId } },
    cache: "no-store",
  });
  if (error || !data) throw new Error("figures fetch failed");
  return data;
}

// Bytes URL for an <img src>. Built from baseUrl like the other non-JSON endpoints.
export function figureUrl(snapshotId: string, figureId: string): string {
  return `${baseUrl}/snapshots/${snapshotId}/figures/${figureId}`;
}
```

- [ ] **Step 2: Write a unit test** — `apps/web/lib/figures.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { figureUrl } from "@gulp/api-client";

describe("figureUrl", () => {
  it("builds a bytes URL from ids", () => {
    expect(figureUrl("snap-1", "fig-2")).toMatch(/\/snapshots\/snap-1\/figures\/fig-2$/);
  });
});
```

- [ ] **Step 3: Run — expect PASS** — `pnpm --filter @gulp/web test -- figures` (run `pnpm install` first if needed). If `@gulp/api-client` needs a build step, run `pnpm --filter @gulp/api-client build` before the web test.

- [ ] **Step 4: Commit**

```bash
git add packages/api-client/src/index.ts apps/web/lib/figures.test.ts
git commit -m "feat(api-client): getFigures + figureUrl helpers"
```

---

### Task 13: Figure gallery picker in the editor

**Files:**
- Modify: `apps/web/components/snapshot/editors/FigureEditor.tsx`
- Modify: `apps/web/lib/packEdit.ts:72-73` (carry `figure_id` through `emptyContent`)
- Test: `apps/web/components/snapshot/editors/FigureEditor.test.tsx` (new)

**Interfaces:**
- Consumes: `getFigures`, `figureUrl` (Task 12); the snapshot id (thread it into the editor — see Step 1). Produces: on save, a `BlockWrite` of shape `{ type: "figure", label, explanation, figure_id }`.

- [ ] **Step 1: Thread the snapshot id to the editor** — `FigureEditor` needs the snapshot id to load the gallery. `PackReport` already has `sid`; pass it down through `BlockCell` → `BlockEditor` → `FigureEditor` as a `snapshotId` prop. Add `snapshotId: string` to the props of `BlockCell`, `BlockEditor`, and `FigureEditor`, and pass `sid`/`snapshotId` through in `PackReport.tsx` (`<BlockCell ... snapshotId={sid} />`), `BlockCell.tsx` (`<BlockEditor ... snapshotId={snapshotId} />`), and `BlockEditor.tsx` (`<FigureEditor ... snapshotId={snapshotId} />`). Other editors ignore it.

- [ ] **Step 2: Write the failing test**

```tsx
// apps/web/components/snapshot/editors/FigureEditor.test.tsx
import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { FigureEditor } from "./FigureEditor";

vi.mock("@gulp/api-client", () => ({
  getFigures: vi.fn(async () => [
    { id: "fig-1", label: "Figure 1", caption: "c", mime_type: "image/png", width: 10, height: 10 },
  ]),
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

describe("FigureEditor gallery", () => {
  beforeEach(() => vi.clearAllMocks());

  it("attaches a picked figure_id on save", async () => {
    const onSave = vi.fn();
    render(
      <FigureEditor
        snapshotId="snap-1"
        block={{ id: "b1", type: "figure", label: "L", explanation: "E", figure_id: null }}
        onSave={onSave}
        onCancel={() => {}}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Figure 1/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ type: "figure", figure_id: "fig-1" }),
      ),
    );
  });
});
```

- [ ] **Step 3: Run — expect failure** — `pnpm --filter @gulp/web test -- FigureEditor`.

- [ ] **Step 4: Implement the picker** — rewrite `FigureEditor.tsx`:

```tsx
"use client";

import React, { useEffect, useState } from "react";
import type { PackBlockOut } from "@gulp/api-client";
import { getFigures, figureUrl, type FigureAssetOut } from "@gulp/api-client";
import type { BlockWrite } from "@/lib/packEdit";
import { EditorShell } from "./EditorShell";
import styles from "../Editing.module.css";

export function FigureEditor({
  snapshotId,
  block,
  onSave,
  onCancel,
}: {
  snapshotId: string;
  block: Extract<PackBlockOut, { type: "figure" }>;
  onSave: (content: BlockWrite) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(block.label);
  const [explanation, setExplanation] = useState(block.explanation);
  const [figureId, setFigureId] = useState<string | null>(block.figure_id ?? null);
  const [gallery, setGallery] = useState<FigureAssetOut[]>([]);

  useEffect(() => {
    let alive = true;
    getFigures(snapshotId)
      .then((figs) => alive && setGallery(figs))
      .catch(() => alive && setGallery([]));
    return () => {
      alive = false;
    };
  }, [snapshotId]);

  return (
    <EditorShell
      onSave={() => onSave({ type: "figure", label, explanation, figure_id: figureId })}
      onCancel={onCancel}
    >
      {gallery.length > 0 && (
        <div className={styles.field}>
          <span>Figures from the paper</span>
          <div className={styles.figureGallery}>
            {gallery.map((f) => (
              <button
                type="button"
                key={f.id}
                aria-label={f.label ?? "figure"}
                aria-pressed={figureId === f.id}
                onClick={() => setFigureId(figureId === f.id ? null : f.id)}
              >
                <img src={figureUrl(snapshotId, f.id)} alt={f.label ?? ""} />
              </button>
            ))}
          </div>
        </div>
      )}
      <div className={styles.field}>
        <label htmlFor="figure-label">Label</label>
        <input id="figure-label" aria-label="Label" className={styles.input}
          value={label} onChange={(e) => setLabel(e.target.value)} />
      </div>
      <div className={styles.field}>
        <label htmlFor="figure-exp">Explanation</label>
        <textarea id="figure-exp" className={styles.textarea}
          value={explanation} onChange={(e) => setExplanation(e.target.value)} />
      </div>
    </EditorShell>
  );
}
```

- [ ] **Step 5: Carry `figure_id` in `emptyContent`** — in `apps/web/lib/packEdit.ts`, change the figure case to `return { type: "figure", label: "", explanation: "", figure_id: null };`.

- [ ] **Step 6: Add minimal gallery styling** — add a `.figureGallery` rule to `apps/web/components/snapshot/Editing.module.css` (flex row, wrap, gap; `img { max-width: 96px; height: auto; }`, selected `button[aria-pressed="true"]` gets an accent outline). Use existing `@gulp/ui` tokens for color.

- [ ] **Step 7: Run — expect PASS** — `pnpm --filter @gulp/web test -- FigureEditor`, then the full `pnpm --filter @gulp/web test`.

- [ ] **Step 8: Commit**

```bash
git add apps/web/components/snapshot/editors/FigureEditor.tsx apps/web/components/snapshot/editors/FigureEditor.test.tsx apps/web/components/snapshot/BlockCell.tsx apps/web/components/snapshot/editors/BlockEditor.tsx apps/web/components/snapshot/PackReport.tsx apps/web/lib/packEdit.ts apps/web/components/snapshot/Editing.module.css
git commit -m "feat(web): figure gallery picker attaches a paper figure to a block"
```

---

### Task 14: Render the attached image in the reader

**Files:**
- Modify: `apps/web/components/snapshot/BlockView.tsx:45-51`
- Test: `apps/web/components/snapshot/BlockView.test.tsx` (new, or extend PackReport.test.tsx)

**Interfaces:**
- Consumes: `figureUrl` (Task 12); `BlockView` needs the snapshot id to build the URL — thread `snapshotId` into `BlockView` like Task 13 did for the editor (via `BlockCell`). Produces: `<img>` when `figure_id` is set, text-only otherwise.

- [ ] **Step 1: Thread `snapshotId` into `BlockView`** — `BlockCell` renders `BlockView`; add a `snapshotId` prop to `BlockView` and pass it from `BlockCell` (which already receives it in Task 13).

- [ ] **Step 2: Write the failing test**

```tsx
// apps/web/components/snapshot/BlockView.test.tsx
import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BlockView } from "./BlockView";

vi.mock("@gulp/api-client", () => ({
  figureUrl: (s: string, f: string) => `/api/${s}/figures/${f}`,
}));

describe("BlockView figure", () => {
  it("renders an img when figure_id is set", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{ id: "b1", type: "figure", label: "Fig 1", explanation: "e", figure_id: "fig-9" }}
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "/api/snap-1/figures/fig-9");
  });

  it("stays text-only when figure_id is null", () => {
    render(
      <BlockView
        snapshotId="snap-1"
        block={{ id: "b1", type: "figure", label: "Fig 1", explanation: "e", figure_id: null }}
      />,
    );
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("Fig 1")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run — expect failure** — `pnpm --filter @gulp/web test -- BlockView`.

- [ ] **Step 4: Update the figure branch** of `BlockView.tsx`:

```tsx
    case "figure":
      return (
        <figure className={styles.figure}>
          {block.figure_id ? (
            <img
              className={styles.figureImage}
              src={figureUrl(snapshotId, block.figure_id)}
              alt={block.label}
            />
          ) : (
            <div className={styles.figureLabel}>{block.label}</div>
          )}
          <figcaption className={styles.explanation}>{block.explanation}</figcaption>
        </figure>
      );
```

Add `import { figureUrl } from "@gulp/api-client";` at the top, and the `snapshotId: string` prop to the `BlockView` signature. Add a `.figureImage` rule (`max-width: 100%; height: auto;`) to `PackReport.module.css`.

- [ ] **Step 5: Run — expect PASS** — `pnpm --filter @gulp/web test -- BlockView`, then the full web suite `pnpm --filter @gulp/web test`.

- [ ] **Step 6: Full gate** — `just lint` and `just test` (both languages) green.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/snapshot/BlockView.tsx apps/web/components/snapshot/BlockCell.tsx apps/web/components/snapshot/BlockView.test.tsx apps/web/components/snapshot/PackReport.module.css
git commit -m "feat(web): render the attached paper figure image in the reader"
```

---

## Self-Review

**Spec coverage:**
- §3 manual gallery pick → Tasks 11–14. Filesystem+API serving → Tasks 1, 11. PDF→PNG → Task 6. Auto/best-effort trigger → Task 9. Hybrid extraction → Tasks 4–7.
- §5.1 shared model/media/setting → Task 1. §5.2 arxiv helpers/tex/tarball/convert/extract/persist/run → Tasks 3–9. §5.3 API schema/service/router + `figure_id` + gen-client → Tasks 10–11. §5.4 web picker + render → Tasks 12–14.
- §6 data model + migration → Tasks 1–2. §7 storage layout → Task 1 (helpers), Tasks 8/11 (write/serve). §8 hybrid detail → Task 7. §9 limits/tar-safety/best-effort → Tasks 5, 7, 9. §10 testing → every task is TDD; the §5.2 URL matrix → Task 3.
- §11 slices map to the three slice headers.

**Placeholder scan:** No TBD/TODO; every code step is complete. The `_figure_block` helper in Task 10 is described by construction (mirror `_block`); acceptable since the exact model calls are given in adjacent tasks.

**Type consistency:** `ExtractedFigure`/`TexRef` defined once (Task 4) and imported everywhere. `extract_figures`→`persist_figures`→`SourceFigure` field names (`order_index`, `ext`, `mime_type`, `width`, `height`) match model (Task 1), migration (Task 2), API schema (Task 11). `figure_id` name consistent across worker schema, API schema, `block_dict` round-trip, web editor, and reader. `figureUrl(snapshotId, figureId)` signature identical in Tasks 12/13/14.

---

## Execution

Slices are independently testable (Slice 1 ships figures end-to-end at the data layer; Slice 2 exposes them; Slice 3 attaches/renders). Recommended: subagent-driven-development, one subagent per task, review between tasks.
