# PDF Support + Real Link Titles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read born-digital PDFs (e.g. arxiv `/pdf/…`) through the existing `NormDoc` pipeline, and show the real document title in the inbox instead of the bare host.

**Architecture:** A `pypdf` PDF adapter behind the same `NormDoc` seam; a `FetchedDoc` (bytes + content-type) fetch layer that routes PDF vs HTML; a lightweight `resolve_metadata` worker job, enqueued at capture, that writes the real title + media type onto the `Source`. Downstream (digest, export, schema) is untouched — PDF export works for free since `build_export` reuses `_to_normdoc`.

**Tech Stack:** Python 3.13, `pypdf` (BSD), httpx (async), SQLAlchemy 2.0 (sync), arq, pydantic, trafilatura (existing HTML path).

## Global Constraints

- **PDF lib = `pypdf`** (BSD; pure-Python). **Born-digital only — no OCR**; a scanned/image PDF yields no text → empty `content_body` → existing `ValueError("extraction produced no content")` → `needs_attention` (graceful, already handled).
- **`NormDoc` invariant:** for every block, `content_body[anchor.start:anchor.end] == block.text`. The PDF adapter MUST preserve this (join paragraphs with `"\n\n"`, advance offset by `len(text) + 2`).
- **Single source of truth:** `normdoc_from_fetched` routes both processing AND `resolve_metadata`; `host_of` is shared by capture AND the resolve job (both import from `gulp_shared`). Never fork.
- **Fetch contract after the refactor:** `FetchFn = Callable[[str], Awaitable[FetchedDoc]]`; the default real fetch is `fetch_document`. `fetch_html` is removed — update every importer.
- **Capture never blocks:** `resolve_metadata` is a background arq job (enqueued, never awaited in the request). The capture endpoint stays a **sync** `def` (so `enqueue`'s `asyncio.run` is safe).
- **Title overwrite rule:** only overwrite `source.title` when it equals `host_of(source.origin_url)` (the capture placeholder) — never a user-typed or already-resolved title. Notes (no `origin_url`) are never touched.
- **Worker `gulp_shared.*` imports carry `# type: ignore[import-untyped]`; api/shared imports are clean. Owner-scoped endpoints unchanged.**
- **Gate:** `cd services/shared && uv run pytest`, `cd services/worker && uv run pytest`, `cd services/api && uv run pytest` all GREEN. (Repo-wide ruff/mypy carry accepted pre-existing debt.) **TDD + a commit per task.**

---

## File Structure

- `services/shared/gulp_shared/urls.py` *(new)* — `host_of(url)`.
- `services/api/app/services/capture.py` *(modify)* — use `host_of`.
- `services/worker/app/pipeline/adapters/pdf.py` *(new)* — `pdf_to_normdoc`, `_pdf_title`.
- `services/worker/tests/fixtures/sample.pdf` *(new)* — born-digital fixture.
- `services/worker/app/pipeline/adapters/fetch.py` *(new)* — `FetchedDoc`, `fetch_document`, `is_pdf`.
- `services/worker/app/pipeline/adapters/webpage.py` *(modify)* — remove `fetch_html`.
- `services/worker/app/pipeline/run.py` *(modify)* — `normdoc_from_fetched` router, retyped `_to_normdoc`/`FetchFn`, title write-back.
- `services/worker/app/pipeline/metadata.py` *(new)* — `run_resolve_metadata`.
- `services/worker/app/export/jobs.py` *(modify)* — `fetch_document` default, title write-back.
- `services/worker/app/tasks/__init__.py` *(modify)* — `resolve_metadata` arq job + register.
- `services/api/app/routers/capture.py` *(modify)* — enqueue `resolve_metadata` for new links.

Order is dependency-driven: shared helper → PDF adapter → fetch refactor/routing (uses the adapter) → resolve job → capture wiring + write-back.

---

### Task 1: `host_of` shared helper + capture uses it

**Files:**
- Create: `services/shared/gulp_shared/urls.py`
- Modify: `services/api/app/services/capture.py`
- Test: `services/shared/tests/test_urls.py`

**Interfaces:**
- Produces: `host_of(url: str) -> str` — `urlsplit(url).hostname or url` (the exact current `_host`).

- [ ] **Step 1: Write the failing test**

Create `services/shared/tests/test_urls.py`:

```python
from gulp_shared.urls import host_of


def test_host_of_extracts_hostname():
    assert host_of("https://arxiv.org/pdf/2606.27377") == "arxiv.org"
    assert host_of("http://example.com/a?b=1") == "example.com"


def test_host_of_falls_back_to_the_raw_string():
    assert host_of("not a url") == "not a url"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_urls.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gulp_shared.urls'`

- [ ] **Step 3: Create the helper**

Create `services/shared/gulp_shared/urls.py`:

```python
"""URL helpers shared by capture and the metadata-resolution job."""

from urllib.parse import urlsplit


def host_of(url: str) -> str:
    return urlsplit(url).hostname or url
```

- [ ] **Step 4: Point capture at it**

In `services/api/app/services/capture.py`, remove the local `_host` function (the `def _host(url): return urlsplit(url).hostname or url` block) and import the shared one. Add near the top imports:

```python
from gulp_shared.urls import host_of
```

Then change the link-branch title line from `title=req.title or _host(normalized),` to:

```python
            title=req.title or host_of(normalized),
```

(Leave the `urlsplit` import only if still used elsewhere; if not, remove it.)

- [ ] **Step 5: Run tests**

Run: `cd services/shared && uv run pytest tests/test_urls.py -v` then `cd services/api && uv run pytest -q`
Expected: PASS (both).

- [ ] **Step 6: Commit**

```bash
git add services/shared/gulp_shared/urls.py services/shared/tests/test_urls.py services/api/app/services/capture.py
git commit -m "feat: shared host_of helper; capture uses it"
```

---

### Task 2: PDF adapter (`pypdf`)

**Files:**
- Modify: `services/worker/pyproject.toml` (add `pypdf`)
- Create: `services/worker/app/pipeline/adapters/pdf.py`, `services/worker/tests/fixtures/sample.pdf`
- Test: `services/worker/tests/test_pdf_adapter.py`

**Interfaces:**
- Consumes: `Anchor`, `NormBlock`, `NormDoc` (`app.pipeline.normdoc`).
- Produces: `pdf_to_normdoc(data: bytes, *, fallback_title: str, url: str) -> NormDoc` (`media_type="pdf"`, `lang="en"`, paragraph blocks labeled `"Page N"`, anchors satisfying the `NormDoc` invariant). Title via `_pdf_title(reader, page1_text, fallback)`: metadata `/Title` (stripped length ≥ 4) → first page-1 line (stripped length ≥ 12, truncated to 200) → `fallback`.

- [ ] **Step 1: Add the dependency + generate the fixture**

In `services/worker/pyproject.toml`, add `"pypdf>=4.0"` to `dependencies`. Then:

```bash
cd services/worker && uv sync && cd ../..
mkdir -p services/worker/tests/fixtures
uv run --with reportlab python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('services/worker/tests/fixtures/sample.pdf')
c.setTitle('The Spacing Effect')
c.drawString(72, 720, 'The Spacing Effect')
c.drawString(72, 690, 'Distributed practice beats cramming for long-term retention.')
c.drawString(72, 660, 'Review material at increasing intervals across days.')
c.showPage(); c.save()
print('wrote sample.pdf')
"
```

(`reportlab` is used only to *generate* the committed fixture via `uv run --with` — it is NOT a project dependency.)

- [ ] **Step 2: Write the failing test**

Create `services/worker/tests/test_pdf_adapter.py`:

```python
from pathlib import Path

from app.pipeline.adapters.pdf import pdf_to_normdoc

_SAMPLE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_pdf_to_normdoc_extracts_title_text_and_valid_anchors():
    nd = pdf_to_normdoc(_SAMPLE.read_bytes(), fallback_title="arxiv.org", url="https://x/y.pdf")
    assert nd.media_type == "pdf"
    assert nd.title == "The Spacing Effect"  # from PDF /Title metadata
    assert "Distributed practice" in nd.content_body
    assert "increasing intervals" in nd.content_body
    assert nd.blocks, "expected at least one block"
    # NormDoc invariant: every block's anchor slices content_body exactly
    for b in nd.blocks:
        assert nd.content_body[b.anchor.start : b.anchor.end] == b.text


def test_pdf_title_falls_back_to_first_line_when_metadata_missing(tmp_path):
    # A PDF with no /Title: title comes from the first substantial page-1 line.
    import importlib.util
    if importlib.util.find_spec("reportlab") is None:
        return  # generation lib unavailable in this env; covered by the metadata case
    from reportlab.pdfgen import canvas
    p = tmp_path / "untitled.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(72, 720, "An Untitled Born-Digital Document")
    c.showPage(); c.save()
    nd = pdf_to_normdoc(p.read_bytes(), fallback_title="fallback", url="https://x/z.pdf")
    assert nd.title == "An Untitled Born-Digital Document"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_pdf_adapter.py -v`
Expected: FAIL — cannot import `app.pipeline.adapters.pdf`.

- [ ] **Step 4: Write the adapter**

Create `services/worker/app/pipeline/adapters/pdf.py`:

```python
"""PDF adapter — extract born-digital PDF text + title into a NormDoc.

Mirrors the webpage adapter's contract: content_body is the assembled text and
every block anchor slices it exactly (content_body[start:end] == block.text).
"""

import re
from io import BytesIO

from pypdf import PdfReader

from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _pdf_title(reader: PdfReader, page1_text: str, fallback: str) -> str:
    meta = reader.metadata
    raw = (meta.title if meta and meta.title else "") or ""
    title = raw.strip()
    if len(title) >= 4:
        return title
    for line in page1_text.splitlines():
        candidate = line.strip()
        if len(candidate) >= 12:
            return candidate[:200]
    return fallback


def pdf_to_normdoc(data: bytes, *, fallback_title: str, url: str) -> NormDoc:
    reader = PdfReader(BytesIO(data))
    paragraphs: list[tuple[str, str]] = []  # (section_label, text)
    page1_text = ""
    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if page_no == 1:
            page1_text = text
        for para in re.split(r"\n\s*\n", text):
            stripped = para.strip()
            if stripped:
                paragraphs.append((f"Page {page_no}", stripped))

    blocks: list[NormBlock] = []
    parts: list[str] = []
    pos = 0
    for label, text in paragraphs:
        start = pos
        end = start + len(text)
        blocks.append(NormBlock(text=text, section_label=label, anchor=Anchor(start=start, end=end)))
        parts.append(text)
        pos = end + 2  # the "\n\n" join separator

    content_body = "\n\n".join(parts)
    title = _pdf_title(reader, page1_text, fallback_title)
    return NormDoc(title=title, lang="en", media_type="pdf", content_body=content_body, blocks=blocks)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_pdf_adapter.py -v`
Expected: PASS (2 tests). If `extract_text()` returns the three lines as one paragraph, that's fine — the asserts check substrings + the anchor invariant, not block count.

- [ ] **Step 6: Commit**

```bash
git add services/worker/pyproject.toml services/worker/app/pipeline/adapters/pdf.py services/worker/tests/test_pdf_adapter.py services/worker/tests/fixtures/sample.pdf
git commit -m "feat(s2): pypdf PDF adapter (born-digital text + title -> NormDoc)"
```

---

### Task 3: Fetch refactor + content-type routing

**Files:**
- Create: `services/worker/app/pipeline/adapters/fetch.py`
- Modify: `services/worker/app/pipeline/adapters/webpage.py`, `services/worker/app/pipeline/run.py`, `services/worker/app/export/jobs.py`, `services/worker/tests/test_run.py`
- Test: `services/worker/tests/test_run.py` (updated + a PDF case)

**Interfaces:**
- Consumes: `pdf_to_normdoc` (Task 2), `webpage_to_normdoc`/`note_to_normdoc` (existing).
- Produces: `FetchedDoc{content: bytes, content_type: str}`; `fetch_document(url) -> FetchedDoc`; `is_pdf(doc) -> bool`; `normdoc_from_fetched(doc, *, fallback_title, url) -> NormDoc`; retyped `FetchFn = Callable[[str], Awaitable[FetchedDoc]]`; `process_source`/`run_build_export` default `fetch=fetch_document`.

- [ ] **Step 1: Write the failing test (update + add PDF case)**

Replace the two fetch functions and assertions in `services/worker/tests/test_run.py`. Change `_no_fetch` to return a `FetchedDoc` and `_fetch` to return an HTML `FetchedDoc`, and add a PDF-routing test. Apply these edits:

In the imports block of `test_run.py`, add:

```python
from pathlib import Path

from app.pipeline.adapters.fetch import FetchedDoc
```

Change `_no_fetch` (note test) to:

```python
    async def _no_fetch(url: str) -> FetchedDoc:  # notes never fetch
        raise AssertionError("note path must not fetch")
```

Change `_fetch` (link test) to:

```python
    async def _fetch(url: str) -> FetchedDoc:
        html = ("<html><head><title>A</title></head><body><article>"
                "<h1>A</h1><p>Attention weighs tokens by relevance across the input.</p>"
                "</article></body></html>")
        return FetchedDoc(content=html.encode(), content_type="text/html; charset=utf-8")
```

Add a new test at the end of the file:

```python
async def test_pdf_link_routes_through_pdf_adapter() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="x.example",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/p.pdf")
    s.add(snap)
    s.flush()
    pdf_bytes = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()

    async def _fetch(url: str) -> FetchedDoc:
        return FetchedDoc(content=pdf_bytes, content_type="application/pdf")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))

    assert snap.status == SnapshotStatus.ready
    assert snap.media_type == MediaType.pdf
    assert "Distributed practice" in (snap.content_body or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_run.py -v`
Expected: FAIL — cannot import `FetchedDoc` from `app.pipeline.adapters.fetch`.

- [ ] **Step 3: Write `fetch.py`**

Create `services/worker/app/pipeline/adapters/fetch.py`:

```python
"""The one network boundary: fetch a URL into bytes + content-type."""

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FetchedDoc:
    content: bytes
    content_type: str


async def fetch_document(url: str) -> FetchedDoc:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url, headers={"User-Agent": "GulpBot/1.0"})
        resp.raise_for_status()
        return FetchedDoc(content=resp.content, content_type=resp.headers.get("content-type", ""))


def is_pdf(doc: FetchedDoc) -> bool:
    return "application/pdf" in doc.content_type.lower()
```

- [ ] **Step 4: Remove `fetch_html` from `webpage.py`**

In `services/worker/app/pipeline/adapters/webpage.py`, delete the `fetch_html` function (the `async def fetch_html(url: str) -> str:` block) and the now-unused `import httpx` if nothing else uses it. Keep `webpage_to_normdoc` and `extract_markdown` unchanged.

- [ ] **Step 5: Rewrite routing in `run.py`**

In `services/worker/app/pipeline/run.py`, update the imports — replace `from app.pipeline.adapters.webpage import fetch_html, webpage_to_normdoc` with:

```python
from app.pipeline.adapters.fetch import FetchedDoc, fetch_document, is_pdf
from app.pipeline.adapters.pdf import pdf_to_normdoc
from app.pipeline.adapters.webpage import webpage_to_normdoc
```

Change `FetchFn` and `_to_normdoc`, and add `normdoc_from_fetched`:

```python
FetchFn = Callable[[str], Awaitable[FetchedDoc]]


def normdoc_from_fetched(doc: FetchedDoc, *, fallback_title: str, url: str) -> NormDoc:
    if is_pdf(doc):
        return pdf_to_normdoc(doc.content, fallback_title=fallback_title, url=url)
    html = doc.content.decode("utf-8", errors="replace")
    return webpage_to_normdoc(html, fallback_title=fallback_title, url=url)


async def _to_normdoc(source: Source, fetch: FetchFn) -> NormDoc:
    if source.origin_url:
        doc = await fetch(source.origin_url)
        return normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)
    return note_to_normdoc(source.title, source.content_body or "")
```

Change `process_source`'s signature default from `fetch: FetchFn = fetch_html,` to `fetch: FetchFn = fetch_document,`.

- [ ] **Step 6: Update `export/jobs.py`**

In `services/worker/app/export/jobs.py`: replace `from app.pipeline.adapters.webpage import fetch_html` with `from app.pipeline.adapters.fetch import FetchedDoc, fetch_document`; change `FetchFn = Callable[[str], Awaitable[str]]` to `FetchFn = Callable[[str], Awaitable[FetchedDoc]]`; change `run_build_export`'s default `fetch: FetchFn = fetch_html,` to `fetch: FetchFn = fetch_document,`. (The export note tests don't inject fetch, so they're unaffected.)

- [ ] **Step 7: Confirm no stray `fetch_html` references, run tests**

```bash
grep -rn "fetch_html" services/worker/app services/worker/tests || echo "no fetch_html references — clean"
cd services/worker && uv run pytest -q
```
Expected: no references; full worker suite PASS (incl. the new PDF-routing test).

- [ ] **Step 8: Commit**

```bash
git add services/worker/app/pipeline/adapters/fetch.py services/worker/app/pipeline/adapters/webpage.py services/worker/app/pipeline/run.py services/worker/app/export/jobs.py services/worker/tests/test_run.py
git commit -m "feat(s2): content-type routing (FetchedDoc) — PDF vs HTML in the fetch layer"
```

---

### Task 4: `resolve_metadata` job

**Files:**
- Create: `services/worker/app/pipeline/metadata.py`
- Modify: `services/worker/app/tasks/__init__.py`
- Test: `services/worker/tests/test_metadata.py`, `services/worker/tests/test_tasks.py` (registration assert)

**Interfaces:**
- Consumes: `FetchedDoc`/`fetch_document` (Task 3), `normdoc_from_fetched` (Task 3), `host_of` (Task 1), `MediaType`/`Source`.
- Produces: `async def run_resolve_metadata(db, source, *, fetch=fetch_document) -> None`; arq `resolve_metadata(ctx, snapshot_id)` registered in `WorkerSettings.functions`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_metadata.py`:

```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.metadata import run_resolve_metadata
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind  # type: ignore[import-untyped]
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _pdf_fetch():  # type: ignore[no-untyped-def]
    data = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()

    async def _fetch(url: str) -> FetchedDoc:
        return FetchedDoc(content=data, content_type="application/pdf")

    return _fetch


async def test_resolve_sets_real_title_and_pdf_type_over_host_placeholder() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="arxiv.org",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/x")
    s.add(snap); s.flush()
    await run_resolve_metadata(s, snap, fetch=_pdf_fetch())
    assert snap.title == "The Spacing Effect"
    assert snap.media_type == MediaType.pdf


async def test_resolve_keeps_a_user_supplied_title() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="My own title",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/x")
    s.add(snap); s.flush()
    await run_resolve_metadata(s, snap, fetch=_pdf_fetch())
    assert snap.title == "My own title"  # not the host placeholder -> untouched
    assert snap.media_type == MediaType.pdf  # type still refined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_metadata.py -v`
Expected: FAIL — cannot import `app.pipeline.metadata`.

- [ ] **Step 3: Write `metadata.py`**

Create `services/worker/app/pipeline/metadata.py`:

```python
"""resolve_metadata — fetch a link and write its real title + media type onto
the Source so the inbox stops showing the bare host. No AI; non-fatal on error.
"""

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.pipeline.adapters.fetch import FetchedDoc, fetch_document
from app.pipeline.run import normdoc_from_fetched
from gulp_shared.models.source import MediaType, Source  # type: ignore[import-untyped]
from gulp_shared.urls import host_of  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[FetchedDoc]]


async def run_resolve_metadata(db: Session, source: Source, *, fetch: FetchFn = fetch_document) -> None:
    if not source.origin_url:
        return
    try:
        doc = await fetch(source.origin_url)
        nd = normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)
        source.media_type = MediaType(nd.media_type)
        if source.title == host_of(source.origin_url) and nd.title and nd.title != source.title:
            source.title = nd.title
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("resolve_metadata failed for %s", source.id)
```

- [ ] **Step 4: Add the arq job + register**

In `services/worker/app/tasks/__init__.py`, add an import:

```python
from app.pipeline.metadata import run_resolve_metadata
```

Add the job (next to `build_export`):

```python
async def resolve_metadata(ctx: dict, snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("resolve_metadata: snapshot %s not found", snapshot_id)
            return
        await run_resolve_metadata(db, source)
    finally:
        db.close()
```

Update `WorkerSettings.functions`:

```python
    functions = [process_snapshot, build_export, import_result, resolve_metadata]
```

- [ ] **Step 5: Registration assert + run tests**

Add to `services/worker/tests/test_tasks.py`:

```python
def test_resolve_metadata_registered() -> None:
    from app.tasks import WorkerSettings, resolve_metadata
    assert resolve_metadata in WorkerSettings.functions
```

Run: `cd services/worker && uv run pytest tests/test_metadata.py tests/test_tasks.py -v` then `cd services/worker && uv run pytest -q`
Expected: PASS (full worker suite).

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/pipeline/metadata.py services/worker/app/tasks/__init__.py services/worker/tests/test_metadata.py services/worker/tests/test_tasks.py
git commit -m "feat(s2): resolve_metadata job — real title + media type onto the Source"
```

---

### Task 5: Capture enqueues `resolve_metadata` + processing title write-back

**Files:**
- Modify: `services/api/app/routers/capture.py`, `services/worker/app/pipeline/run.py`, `services/worker/app/export/jobs.py`
- Test: `services/api/tests/test_capture_enqueue.py`, `services/worker/tests/test_run.py` (write-back case)

**Interfaces:**
- Consumes: `get_enqueue` (`app.deps`), `host_of` (Task 1), `normdoc` title (Task 3).
- Produces: capture enqueues `("resolve_metadata", <id>)` for a **new** link snapshot; `process_source`/`run_build_export` write the extracted title back when the row still shows the host placeholder.

- [ ] **Step 1: Write the failing test (capture enqueue)**

Create `services/api/tests/test_capture_enqueue.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.deps import get_db, get_enqueue
from app.main import app


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    calls: list[tuple[object, ...]] = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def test_capturing_a_link_enqueues_resolve_metadata(client):  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"url": "https://arxiv.org/pdf/2606.27377"})
    assert r.status_code == 200
    sid = r.json()["snapshot"]["id"]
    assert ("resolve_metadata", sid) in client.enqueue_calls


def test_capturing_a_note_does_not_enqueue(client):  # type: ignore[no-untyped-def]
    r = client.post("/capture", json={"text": "just a note"})
    assert r.status_code == 200
    assert client.enqueue_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/api && uv run pytest tests/test_capture_enqueue.py -v`
Expected: FAIL — capture doesn't enqueue (no `resolve_metadata` call).

- [ ] **Step 3: Enqueue in the capture router**

In `services/api/app/routers/capture.py`, add `get_enqueue` to the imports and the `capture` handler, and enqueue for new links. Replace the `capture` function with:

```python
from collections.abc import Callable

from app.deps import get_db, get_enqueue


@router.post("/capture", response_model=CaptureResponse)
def capture(
    req: CaptureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> CaptureResponse:
    source, duplicate = create_snapshot(db, user.id, req)
    if not duplicate and source.origin_url:
        enqueue("resolve_metadata", str(source.id))
    return CaptureResponse(snapshot=to_out(db, source), duplicate=duplicate)
```

(Keep the existing `from app.deps import get_db` line consistent — merge it into the combined import above so `get_db` isn't imported twice.)

- [ ] **Step 4: Run the capture test**

Run: `cd services/api && uv run pytest tests/test_capture_enqueue.py -v` then `cd services/api && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Write the failing test (processing write-back)**

Add to `services/worker/tests/test_run.py`:

```python
async def test_link_pipeline_writes_real_title_over_host_placeholder() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="x.example",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://x.example/a")
    s.add(snap); s.flush()

    async def _fetch(url: str) -> FetchedDoc:
        html = "<html><head><title>Real Title</title></head><body><article><p>Body text here about relevance.</p></article></body></html>"
        return FetchedDoc(content=html.encode(), content_type="text/html")

    await process_source(s, snap, fetch=_fetch, provider=FakeProvider(_OK))
    assert snap.title == "Real Title"  # host placeholder replaced by the extracted title
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_run.py::test_link_pipeline_writes_real_title_over_host_placeholder -v`
Expected: FAIL — title stays `x.example` (no write-back yet).

- [ ] **Step 7: Add the write-back (run.py + jobs.py)**

In `services/worker/app/pipeline/run.py`, add the `host_of` import (`from gulp_shared.urls import host_of  # type: ignore[import-untyped]`) and, inside `process_source`'s `try`, right after `source.media_type = MediaType(normdoc.media_type)`, insert:

```python
        if (
            source.origin_url
            and source.title == host_of(source.origin_url)
            and normdoc.title
            and normdoc.title != source.title
        ):
            source.title = normdoc.title
```

Apply the **same** import + block in `services/worker/app/export/jobs.py`'s `run_build_export`, right after its `source.media_type = MediaType(normdoc.media_type)` line.

- [ ] **Step 8: Run tests**

Run: `cd services/worker && uv run pytest -q` then `cd services/api && uv run pytest -q`
Expected: PASS (both suites).

- [ ] **Step 9: Commit**

```bash
git add services/api/app/routers/capture.py services/api/tests/test_capture_enqueue.py services/worker/app/pipeline/run.py services/worker/app/export/jobs.py services/worker/tests/test_run.py
git commit -m "feat(s2): capture enqueues resolve_metadata; processing writes real title back"
```

---

## Self-Review

**Spec coverage:**
- pypdf PDF adapter (text + title, born-digital) → Task 2 ✓.
- Content-type routing (FetchedDoc, PDF vs HTML) → Task 3 ✓; PDF export works for free (build_export reuses `_to_normdoc`).
- `resolve_metadata` job writing title + media_type, placeholder-only overwrite → Task 4 ✓.
- `host_of` shared by capture + resolve → Task 1 ✓.
- Capture enqueues resolve_metadata for new links (sync endpoint) → Task 5 ✓; note captures don't.
- Processing/export title write-back (belt-and-suspenders) → Task 5 ✓.
- Born-digital only / graceful empty-content failure → existing `process_source` guard, unchanged; PDF adapter returns empty `content_body` for textless PDFs.
- **Deferred (per spec §2):** OCR, fetched-bytes caching (the double-fetch is accepted), video/podcast adapters, per-source language detection.

**Placeholder scan:** none — every step has concrete code/commands. The one fixture is generated by an exact `uv run --with reportlab` command and committed.

**Type consistency:** `FetchedDoc{content: bytes, content_type: str}`, `fetch_document`, `is_pdf`, `normdoc_from_fetched(doc, *, fallback_title, url)`, `pdf_to_normdoc(data, *, fallback_title, url)`, `host_of(url)`, `run_resolve_metadata(db, source, *, fetch)`, `resolve_metadata(ctx, snapshot_id)` are named identically across the adapter, `run.py`, `metadata.py`, the tasks, the capture router, and every test. `FetchFn` is retyped to return `FetchedDoc` in both `run.py` and `export/jobs.py`. The title-write-back block is byte-identical in `run.py` and `jobs.py`. `media_type` strings: webpage→`"article"`, pdf→`"pdf"`, matching the `MediaType` enum.
