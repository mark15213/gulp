# arxiv-aware Title Resolution — design

*Gulp · feature design · 2026-06-26 · brainstorm output*

> A live test of PDF support showed the generic PDF title heuristic grabbing license boilerplate ("Provided proper attribution is provided, Google hereby grants permission to…") for an arxiv paper, because that PDF carries no `/Info` or XMP title and the real title sits on page-1 line 4. arxiv is the dominant PDF source for a learning app, and its **abstract page** exposes a clean `<meta name="citation_title">`. This makes `resolve_metadata` arxiv-aware: for an arxiv link, take the title from the abs page instead of the PDF text.

## 1. Scope

- **In:** an `arxiv` adapter (`arxiv_abs_url` URL→abs-URL, `arxiv_title` abs-page→`citation_title`) and wiring it into `run_resolve_metadata` so an arxiv link's inbox title is the canonical paper title. Self-contained and non-fatal — any failure falls back to today's behavior.
- **Out (unchanged / deferred):** the general non-arxiv PDF title heuristic stays the documented v1 best-effort (`_pdf_title`); the processing/export title write-back keeps that generic fallback (it only fires when `resolve_metadata` didn't run); no new HTML-parser dependency (a regex reads the one meta tag); no other arxiv metadata (authors, abstract).

## 2. The unit — `services/worker/app/pipeline/adapters/arxiv.py`

- `arxiv_abs_url(url: str) -> str | None` — **pure.** `None` unless the host is `arxiv.org` / `www.arxiv.org` / `export.arxiv.org` and the path matches `^/(?:pdf|abs)/(.+?)(?:\.pdf)?$`. Returns `https://arxiv.org/abs/<id>`, where `<id>` is the captured group (handles new ids `1706.03762`, versioned `1706.03762v7`, `.pdf`-suffixed, and old slash ids `cs/0112017`; the abs page resolves with or without a version).
- `async def arxiv_title(url: str, *, fetch: FetchFn = fetch_document) -> str | None` — if `arxiv_abs_url(url)` is `None`, return `None` **without fetching** (non-arxiv pays nothing). Otherwise `fetch` the abs URL, decode (`errors="replace"`), and return the first `<meta name="citation_title" content="…">` value (regex `_CITATION_TITLE`, case-insensitive, name-before-content as arxiv emits), stripped; `None` on any fetch/parse failure (wrapped in `try/except` → `None`).
- `FetchFn = Callable[[str], Awaitable[FetchedDoc]]` (same contract as the rest of the pipeline; reuses `FetchedDoc`/`fetch_document` from `adapters/fetch.py`).

## 3. Wiring — `run_resolve_metadata` only

Replace the title selection so arxiv wins, generic is the fallback:

```python
nd = normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)
source.media_type = MediaType(nd.media_type)                       # unchanged — from the real fetch
title = (await arxiv_title(source.origin_url, fetch=fetch)) or nd.title
if source.title == host_of(source.origin_url) and title and title != source.title:
    source.title = title
```

For an arxiv `/pdf/` capture this performs one extra small fetch (the abs page) on top of the existing PDF fetch — acceptable for the background metadata job. Non-arxiv URLs do **zero** extra work (`arxiv_title` returns `None` before fetching). The `media_type`, the placeholder-only overwrite rule, and the non-fatal `try/except` of `run_resolve_metadata` are all unchanged.

## 4. Error handling

`arxiv_title` never raises — fetch/decode/regex failures all return `None`, and the caller falls back to `nd.title`. So a flaky arxiv, an HTML change, or a non-matching page degrades to exactly today's behavior (generic title or the host placeholder), never a crash. `run_resolve_metadata` remains non-fatal overall.

## 5. Testing (hermetic — no network)

- `arxiv_abs_url`: `/pdf/1706.03762`, `/pdf/1706.03762v7`, `/pdf/1706.03762.pdf`, `/abs/1706.03762`, old `/abs/cs/0112017` → the right abs URL; `https://example.com/x`, a non-arxiv host, and a non-pdf/abs arxiv path → `None`.
- `arxiv_title`: an injected `fetch` returning a fixture abs-HTML containing `<meta name="citation_title" content="Attention Is All You Need">` → returns that string; a non-arxiv URL → `None` **and the injected fetch is asserted never called**; a fetch that raises / HTML without the meta → `None`.
- `run_resolve_metadata` (extends `test_metadata.py`): an arxiv `/pdf/` URL with an injected fetch that **branches on URL** (PDF fixture bytes for `/pdf/…`, abs-HTML for `/abs/…`) and a host-placeholder title → `source.title` becomes "Attention Is All You Need" and `media_type == pdf`. The existing non-arxiv resolve tests stay green (arxiv path inert).

## 6. Decomposition — one short plan

1. `arxiv.py` — `arxiv_abs_url` + `arxiv_title` + unit tests (pure URL cases + the injected-fetch title cases).
2. Wire `arxiv_title` into `run_resolve_metadata` + the arxiv resolve test.
