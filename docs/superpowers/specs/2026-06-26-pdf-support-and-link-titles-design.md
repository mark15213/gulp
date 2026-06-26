# PDF Support + Real Link Titles — design

*Gulp · feature design · 2026-06-26 · brainstorm output*

> Two gaps surfaced while testing the export executor: (1) Gulp can't read **PDFs** (an arxiv `/pdf/…` link fetches fine but the HTML extractor produces no text → "no readable content"), and (2) a captured link shows its **host** ("arxiv.org") as the title instead of the real document title. Both live in the same fetch/extract layer, so they're designed together.

## 1. Why these belong together

Every source flows through `_to_normdoc` (fetch → adapt → `NormDoc`). Today that path assumes HTML and discards the title the webpage adapter already extracts. PDF support is a new adapter behind the **same `NormDoc` seam** — nothing downstream (digest, export, schema) changes. Real titles reuse the *same fetch + adapter*, just taking the title instead of the body. `MediaType.pdf` already exists in the enum, so no model change for the type.

## 2. Scope

- **In:** a `pypdf` PDF adapter (born-digital PDFs → text + title → `NormDoc`); content-type-based routing (PDF vs HTML) in the fetch layer; a lightweight `resolve_metadata` worker job, enqueued at capture, that fetches a link and writes the real **title** + **media_type** onto the `Source` so the inbox shows them; a shared `host_of` helper.
- **Out (deferred):** OCR for scanned/image-only PDFs (they extract no text and fall to the graceful "couldn't read this source" failure already shipped); caching the fetched bytes to avoid the v1 double-fetch (§8); video/podcast/audio adapters; per-source language detection (v1 stamps `lang="en"`; the digest re-authors to English regardless).

## 3. Architecture & data flow

```
Capture a link → Source.title = host placeholder (instant; capture never blocks)
              → enqueue resolve_metadata(snapshot_id)            [background worker, no AI]
resolve_metadata: fetch URL → route by Content-Type → run adapter
              → update Source {media_type; title (only if still the host placeholder)}   ← inbox shows the real title + type
Start / Export: _to_normdoc → fetch → route by Content-Type
              → pdf_to_normdoc (pypdf) | webpage_to_normdoc → NormDoc → digest / export   [downstream unchanged]
```

PDF **export works for free**: `build_export` already calls `_to_normdoc`, so once routing lands, a PDF snapshot exports a job archive like any other.

## 4. Fetch refactor + content-type routing

Today `fetch_html(url) -> str` assumes HTML. Replace with a shared fetcher that preserves bytes + type:

- `services/worker/app/pipeline/adapters/fetch.py` (new):
  - `@dataclass(frozen=True) class FetchedDoc: content: bytes; content_type: str`
  - `async def fetch_document(url: str) -> FetchedDoc` — httpx `AsyncClient(follow_redirects=True, timeout=30)`, UA `GulpBot/1.0`, `raise_for_status()`, returns `FetchedDoc(resp.content, resp.headers.get("content-type", ""))`.
  - `def is_pdf(doc: FetchedDoc) -> bool: return "application/pdf" in doc.content_type.lower()`
- `services/worker/app/pipeline/run.py` (modify):
  - `def normdoc_from_fetched(doc: FetchedDoc, *, fallback_title: str, url: str) -> NormDoc` — `is_pdf` → `pdf_to_normdoc(doc.content, …)`, else `webpage_to_normdoc(doc.content.decode("utf-8", errors="replace"), …)`. Shared by processing **and** `resolve_metadata`.
  - `_to_normdoc(source, fetch)` → for a link: `doc = await fetch(url)`; `return normdoc_from_fetched(doc, fallback_title=source.title, url=source.origin_url)`. Note path unchanged.
  - `FetchFn = Callable[[str], Awaitable[FetchedDoc]]`; default `fetch = fetch_document`.
- `webpage.py` (modify): drop `fetch_html` (moves to `fetch.py`); keep `webpage_to_normdoc(html: str, …)` unchanged.
- **Blast radius:** `process_source` and `export/jobs.py:run_build_export` take `fetch=fetch_document`; their tests (and the export-job tests) now inject a `FetchedDoc` (e.g. `FetchedDoc(b"<html>…", "text/html")`) instead of a bare HTML string.

## 5. PDF adapter (`adapters/pdf.py`)

- Dependency: **`pypdf`** (BSD; pure-Python; added to `services/worker`).
- `pdf_to_normdoc(data: bytes, *, fallback_title: str, url: str) -> NormDoc`:
  - `reader = PdfReader(BytesIO(data))`; per page, `page.extract_text()`; split each page into paragraphs (blank-line split, mirroring the webpage adapter); each non-empty paragraph → a `NormBlock` with `section_label=f"Page {n}"` and an `Anchor(start, end)` slicing the assembled `content_body`.
  - `content_body` = the paragraphs joined with `"\n\n"`; anchors index into it exactly (same contract as the webpage adapter).
  - `media_type = "pdf"`, `lang = "en"`.
  - **Title heuristic** `_pdf_title(reader, page1_text, fallback)`: `reader.metadata.title` if it's a meaningful string (stripped length ≥ 4) → else the first page-1 line of stripped length ≥ 12 (truncated to 200) → else `fallback`.
- Born-digital only: a scanned PDF yields little/no text → empty `content_body` → the existing `ValueError("extraction produced no content")` path → `needs_attention` → the accurate "couldn't read this source" message (already shipped). No OCR.

## 6. Real titles: `resolve_metadata` job + capture wiring

- `services/shared/gulp_shared/urls.py` (new): `def host_of(url: str) -> str: return urlsplit(url).hostname or url` — the exact current `_host`. `capture.py` imports it (replacing its local `_host`); the resolve job uses it to detect the placeholder. One source of truth, no api↔worker coupling (both depend on `gulp_shared`).
- `services/worker/app/pipeline/metadata.py` (new): `async def run_resolve_metadata(db, source, *, fetch=fetch_document) -> None` —
  - no-op if `source.origin_url` is falsy.
  - `doc = await fetch(url)`; `nd = normdoc_from_fetched(doc, fallback_title=source.title, url=url)`.
  - `source.media_type = MediaType(nd.media_type)`.
  - if `source.title == host_of(url)` **and** `nd.title` and `nd.title != source.title` → `source.title = nd.title`. (Only overwrite the host placeholder — never a user-typed title or an already-resolved one.)
  - commit. On any exception → rollback + log + leave the placeholder (non-fatal; the title just stays the host).
- `services/worker/app/tasks/__init__.py` (modify): arq wrapper `resolve_metadata(ctx, snapshot_id)` (open `SessionLocal`, load `Source`, delegate, close) + register in `WorkerSettings.functions`.
- `services/api` capture (modify the **router**, keeping `create_snapshot` pure): when `create_snapshot` returns a **new** snapshot (`existed is False`) that has `origin_url`, `enqueue("resolve_metadata", str(source.id))`. The capture endpoint is sync, so `enqueue` (asyncio.run) is safe. Dedup hits (`existed is True`) do not re-enqueue.
- Belt-and-suspenders: `process_source` / `run_build_export`, after building the `NormDoc` for a **link** snapshot (`source.origin_url` set), write `source.title = normdoc.title` **iff** `source.title == host_of(source.origin_url)` and `normdoc.title` differs — so a real title still lands even if the resolve job failed or was skipped. (Note snapshots have no `origin_url` and are untouched.)

## 7. Error handling

- **Fetch failure** (404/network) at processing/export → `needs_attention` (unchanged). In `resolve_metadata` → logged, placeholder kept (the inbox just shows the host; non-fatal).
- **No extractable text** (scanned PDF / empty page) → `ValueError("extraction produced no content")` → `needs_attention` → graceful UI message.
- **Corrupt/invalid PDF** → pypdf raises → same `needs_attention` path; `resolve_metadata` swallows + logs.

## 8. Known v1 trade-off — double fetch

A link is fetched twice: once by `resolve_metadata` (title at capture) and again at Start/Export (full extraction). Accepted for v1 (personal tool, bounded cost). The main cost is downloading a large PDF twice. **Future optimization:** persist the fetched bytes / `content_body` from `resolve_metadata` and let processing reuse it — deferred because it intersects the (also-deferred) blob-storage layer.

## 9. Module design

```
gulp_shared/urls.py            host_of(url)                                        (pure; shared by capture + resolve)
worker adapters/fetch.py       FetchedDoc, fetch_document, is_pdf                   (the one network boundary)
worker adapters/pdf.py         pdf_to_normdoc, _pdf_title                           (pure given bytes; pypdf)
worker adapters/webpage.py     webpage_to_normdoc (unchanged); fetch_html removed
worker pipeline/run.py         normdoc_from_fetched (router) + _to_normdoc          (routes by content-type)
worker pipeline/metadata.py    run_resolve_metadata                                 (title/type → Source)
worker tasks/__init__.py       resolve_metadata arq job + register
api capture (router)           enqueue resolve_metadata for new link snapshots; host_of from gulp_shared
```

Each unit has one responsibility; `pdf_to_normdoc`/`host_of`/`normdoc_from_fetched`/`_pdf_title` are unit-testable without network or DB. `fetch_document` is the only piece that touches the network — everything else takes bytes.

## 10. Testing (hermetic)

- **PDF adapter:** a tiny committed fixture PDF (`tests/fixtures/sample.pdf`, born-digital, a known title + a couple paragraphs) → `pdf_to_normdoc` extracts the text into blocks and the title; an empty/garbage PDF → raises or yields empty `content_body`.
- **Routing:** `normdoc_from_fetched` sends `application/pdf` to the PDF path and `text/html` to the webpage path (injected `FetchedDoc`s).
- **resolve_metadata:** with an injected fetch returning a PDF `FetchedDoc`, a snapshot whose title equals the host gets its title + `media_type=pdf` updated; a snapshot with a user title is left untouched. SQLite, no network.
- **Capture wiring:** capturing a new link enqueues `resolve_metadata`; a dedup hit does not.
- **Regression:** update the existing `process_source` / export-job tests to inject `FetchedDoc` and stay green.

## 11. Decomposition — a single plan, module-by-module

1. `host_of` in `gulp_shared/urls.py` + swap `capture.py` to use it.
2. Fetch refactor: `adapters/fetch.py` (`FetchedDoc`/`fetch_document`/`is_pdf`) + `normdoc_from_fetched` routing + `FetchFn` retype + fix the existing fetch-injecting tests.
3. PDF adapter: `pypdf` dep + `adapters/pdf.py` + a fixture PDF + routing wired to it.
4. `resolve_metadata` core (`pipeline/metadata.py`) + arq job + register.
5. Capture enqueues `resolve_metadata` for new links + the processing title write-back.

Order is dependency-driven (shared helper → fetch/routing → PDF adapter → resolve job → capture wiring).
