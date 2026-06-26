# arxiv-aware Title Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For an arxiv link, set the inbox title from the abstract page's canonical `citation_title` instead of the PDF's (often boilerplate) first line.

**Architecture:** A small, self-contained `arxiv` adapter (`arxiv_abs_url` + `arxiv_title`) wired into `run_resolve_metadata` only. Non-arxiv URLs do zero extra work; any arxiv fetch/parse failure falls back to today's generic title.

**Tech Stack:** Python 3.13, httpx (via the existing `fetch_document`), `re` (no new HTML-parser dep).

## Global Constraints

- **arxiv-only:** `arxiv_title` returns `None` (no fetch) for any non-arxiv URL; the generic `_pdf_title` heuristic is untouched.
- **Non-fatal:** `arxiv_title` never raises — fetch/decode/regex failures all return `None`, and the caller falls back to `nd.title`. `run_resolve_metadata` stays non-fatal.
- **No new dependency:** read the one `citation_title` meta tag with a regex.
- **Fetch contract:** `FetchFn = Callable[[str], Awaitable[FetchedDoc]]` (reuse `FetchedDoc`/`fetch_document` from `app.pipeline.adapters.fetch`).
- **Worker `gulp_shared.*` imports carry `# type: ignore[import-untyped]`.**
- **Gate:** `cd services/worker && uv run pytest` GREEN. (Repo-wide ruff/mypy carry accepted debt.) **TDD + a commit per task.**

---

## File Structure

- `services/worker/app/pipeline/adapters/arxiv.py` *(new)* — `arxiv_abs_url`, `arxiv_title`.
- `services/worker/app/pipeline/metadata.py` *(modify)* — `run_resolve_metadata` prefers `arxiv_title`.

---

### Task 1: `arxiv.py` adapter

**Files:**
- Create: `services/worker/app/pipeline/adapters/arxiv.py`
- Test: `services/worker/tests/test_arxiv.py`

**Interfaces:**
- Consumes: `FetchedDoc`, `fetch_document` (`app.pipeline.adapters.fetch`).
- Produces: `arxiv_abs_url(url: str) -> str | None`; `async def arxiv_title(url: str, *, fetch: FetchFn = fetch_document) -> str | None`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_arxiv.py`:

```python
import pytest

from app.pipeline.adapters.arxiv import arxiv_abs_url, arxiv_title
from app.pipeline.adapters.fetch import FetchedDoc

_ABS_HTML = (
    '<html><head>'
    '<meta name="citation_title" content="Attention Is All You Need">'
    '<title>[1706.03762] Attention Is All You Need</title>'
    '</head><body>...</body></html>'
)


def test_arxiv_abs_url_normalizes_the_url_forms():
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762v7") == "https://arxiv.org/abs/1706.03762v7"
    assert arxiv_abs_url("https://arxiv.org/pdf/1706.03762.pdf") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/abs/1706.03762") == "https://arxiv.org/abs/1706.03762"
    assert arxiv_abs_url("https://arxiv.org/abs/cs/0112017") == "https://arxiv.org/abs/cs/0112017"


def test_arxiv_abs_url_returns_none_for_non_arxiv():
    assert arxiv_abs_url("https://example.com/pdf/x") is None
    assert arxiv_abs_url("https://arxiv.org/list/cs.CL/recent") is None
    assert arxiv_abs_url("not a url") is None


async def test_arxiv_title_reads_citation_title():
    async def _fetch(url: str) -> FetchedDoc:
        assert url == "https://arxiv.org/abs/1706.03762"
        return FetchedDoc(content=_ABS_HTML.encode(), content_type="text/html")

    assert await arxiv_title("https://arxiv.org/pdf/1706.03762", fetch=_fetch) == "Attention Is All You Need"


async def test_arxiv_title_non_arxiv_returns_none_without_fetching():
    async def _fetch(url: str) -> FetchedDoc:
        raise AssertionError("must not fetch for a non-arxiv url")

    assert await arxiv_title("https://example.com/p.pdf", fetch=_fetch) is None


async def test_arxiv_title_swallows_failures():
    async def _boom(url: str) -> FetchedDoc:
        raise RuntimeError("network down")

    assert await arxiv_title("https://arxiv.org/pdf/1706.03762", fetch=_boom) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_arxiv.py -v`
Expected: FAIL — cannot import `app.pipeline.adapters.arxiv`.

- [ ] **Step 3: Write the adapter**

Create `services/worker/app/pipeline/adapters/arxiv.py`:

```python
"""arxiv adapter — resolve the canonical paper title from the abstract page.

arxiv PDFs frequently carry no /Title metadata and lead with a license header,
so the generic PDF heuristic mis-titles them. The abstract page exposes a clean
<meta name="citation_title">, which we use instead — for arxiv URLs only.
"""

import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from app.pipeline.adapters.fetch import FetchedDoc, fetch_document

FetchFn = Callable[[str], Awaitable[FetchedDoc]]

_ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
_ARXIV_PATH = re.compile(r"^/(?:pdf|abs)/(.+?)(?:\.pdf)?$")
_CITATION_TITLE = re.compile(
    r'<meta[^>]+name=["\']citation_title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def arxiv_abs_url(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in _ARXIV_HOSTS:
        return None
    m = _ARXIV_PATH.match(parts.path)
    if not m:
        return None
    return f"https://arxiv.org/abs/{m.group(1)}"


async def arxiv_title(url: str, *, fetch: FetchFn = fetch_document) -> str | None:
    abs_url = arxiv_abs_url(url)
    if abs_url is None:
        return None
    try:
        doc = await fetch(abs_url)
        html = doc.content.decode("utf-8", errors="replace")
    except Exception:
        return None
    m = _CITATION_TITLE.search(html)
    return m.group(1).strip() if m else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_arxiv.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/adapters/arxiv.py services/worker/tests/test_arxiv.py
git commit -m "feat(s2): arxiv adapter — canonical title from the abstract page"
```

---

### Task 2: wire `arxiv_title` into `run_resolve_metadata`

**Files:**
- Modify: `services/worker/app/pipeline/metadata.py`
- Test: `services/worker/tests/test_metadata.py` (add an arxiv case)

**Interfaces:**
- Consumes: `arxiv_title` (Task 1).
- Produces: `run_resolve_metadata` prefers the arxiv title over the generic `nd.title` when the URL is arxiv.

- [ ] **Step 1: Write the failing test**

Add to `services/worker/tests/test_metadata.py`:

```python
async def test_resolve_uses_arxiv_abstract_title_for_a_pdf_link() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="arxiv.org",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.webpage,
                  origin_url="https://arxiv.org/pdf/1706.03762")
    s.add(snap); s.flush()

    pdf = (Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()
    abs_html = ('<html><head><meta name="citation_title" '
                'content="Attention Is All You Need"></head><body>x</body></html>')

    async def _fetch(url: str) -> FetchedDoc:
        if "/abs/" in url:
            return FetchedDoc(content=abs_html.encode(), content_type="text/html")
        return FetchedDoc(content=pdf, content_type="application/pdf")

    await run_resolve_metadata(s, snap, fetch=_fetch)
    assert snap.title == "Attention Is All You Need"  # from the abstract page, not the PDF first line
    assert snap.media_type == MediaType.pdf            # still from the real (PDF) fetch
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_metadata.py::test_resolve_uses_arxiv_abstract_title_for_a_pdf_link -v`
Expected: FAIL — `snap.title` is the PDF's first-line heuristic, not "Attention Is All You Need".

- [ ] **Step 3: Wire it in**

In `services/worker/app/pipeline/metadata.py`, add the import (after the `from app.pipeline.run import normdoc_from_fetched` line):

```python
from app.pipeline.adapters.arxiv import arxiv_title
```

Then replace the title block inside `run_resolve_metadata` — change:

```python
        source.media_type = MediaType(nd.media_type)
        if source.title == host_of(source.origin_url) and nd.title and nd.title != source.title:
            source.title = nd.title
        db.commit()
```

to:

```python
        source.media_type = MediaType(nd.media_type)
        title = (await arxiv_title(source.origin_url, fetch=fetch)) or nd.title
        if source.title == host_of(source.origin_url) and title and title != source.title:
            source.title = title
        db.commit()
```

- [ ] **Step 4: Run tests**

Run: `cd services/worker && uv run pytest tests/test_metadata.py -v` then `cd services/worker && uv run pytest -q`
Expected: PASS — the new arxiv case plus the existing resolve tests (the non-arxiv ones are unaffected: `arxiv_title` returns `None` for their URLs and falls back to `nd.title`), full worker suite green.

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/pipeline/metadata.py services/worker/tests/test_metadata.py
git commit -m "feat(s2): resolve_metadata prefers the arxiv abstract title"
```

---

## Self-Review

**Spec coverage:**
- `arxiv_abs_url` (URL forms + non-arxiv → None) → Task 1 ✓.
- `arxiv_title` (citation_title via regex; no-fetch for non-arxiv; non-fatal → None) → Task 1 ✓.
- Wiring into `run_resolve_metadata` only (arxiv preferred, generic fallback; media_type + placeholder rule unchanged) → Task 2 ✓.
- Hermetic tests (injected fetch, branch-on-URL, no network) → Tasks 1–2 ✓.
- **Deferred (per spec §1):** the general non-arxiv PDF heuristic, the processing/export write-back (keeps the generic fallback), other arxiv metadata.

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `arxiv_abs_url(url) -> str | None`, `arxiv_title(url, *, fetch) -> str | None`, `FetchFn = Callable[[str], Awaitable[FetchedDoc]]`, `FetchedDoc` are used identically in the adapter, the wiring, and both tests. The wiring reuses the same `fetch` already passed into `run_resolve_metadata`, so the arxiv abs fetch is injectable in tests (the branch-on-URL fetch).
