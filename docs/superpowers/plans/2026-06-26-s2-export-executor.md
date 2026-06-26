# S2 Export Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an `unprocessed` snapshot's digest job be downloaded as a self-contained `.zip`, run by the user in Claude Code, and uploaded back — populating the same `KnowledgePack` the inline path would, with no Anthropic call.

**Architecture:** A new worker `app/export/` module with pure, independently-testable units (`archive`, `manifest`, `templates`, `builder`, `importer`) plus two thin orchestration cores (`jobs.py`) wrapped by arq tasks. The archive carries a `NormDoc` + a `CLAUDE.md` generated from the inline digest prompt + the `DigestResult` JSON Schema + a `result/` slot. Import reuses `persist_pack`; the build reuses `_to_normdoc`. The API stays thin (enqueue, stream the stashed file, stdlib-only shallow upload checks). A new `exported` snapshot status tracks the hand-off.

**Tech Stack:** Python 3.13, FastAPI (+ `python-multipart` for uploads), SQLAlchemy 2.0 (sync), arq, pydantic 2, stdlib `zipfile`/`hashlib`, Next.js web.

## Global Constraints

- **Single source of truth — never fork:** the `CLAUDE.md` body is generated from the inline digest prompt `app/prompts/digest.py:_SYSTEM`; the output schema is `DigestResult.model_json_schema()`; import validates via `DigestResult.model_validate`; the build reuses `_to_normdoc`; persistence reuses `persist_pack`.
- **No api→worker import:** the API shallow check uses **stdlib `zipfile`** only; all worker-code reuse (`read_zip`, `DigestResult`, `persist_pack`) happens in the worker `import_result` job. The api and worker share `settings.export_dir` (same host).
- **Import validation is strict, two-stage:** API shallow-sync (valid zip · a `manifest.json` whose `snapshot_id`==URL id and `owner_id`==caller · a `result/pack.json` present) → **422** on failure; worker deep-async (zip-slip-safe unzip + size cap → `DigestResult.model_validate`) → `persist_pack` → `ready`; any deep failure → back to `exported` + logged reason.
- **`exported` status:** capture stays `unprocessed`; **Export** → worker builds → `exported`; **Upload** → `ready`. `exported` is still ▶ Start-able (inline remains an alternative) and re-exportable.
- **Worker `gulp_shared.*` imports carry `# type: ignore[import-untyped]`; api imports `gulp_shared` without it. Owner-scoped endpoints (404 on missing/foreign/deleted).**
- **English everywhere** incl. the generated `CLAUDE.md`/`README.md`.
- **Gate:** `cd services/worker && uv run pytest`, `cd services/api && uv run pytest`, and `pnpm --filter @gulp/web test` + `pnpm --filter @gulp/web build` all GREEN. (Repo-wide ruff/mypy/eslint carry accepted pre-existing debt.)
- **Hermetic tests:** injected `fetch`, in-memory SQLite, a tmp `export_dir`; no network, no API key. **TDD + a commit per task.**

---

## File Structure

- `services/shared/gulp_shared/models/source.py` *(modify)* — `SnapshotStatus.exported`.
- `services/shared/gulp_shared/settings.py` *(modify)* — `export_dir`.
- `services/api/alembic/versions/<rev>_s2_exported_status.py` *(new)* — `ADD VALUE 'exported'`.
- `services/worker/app/export/archive.py` *(new)* — `write_zip` / `read_zip` (zip-slip + size guards).
- `services/worker/app/export/manifest.py` *(new)* — `FORMAT_VERSION`, `build_manifest`, `parse_manifest`.
- `services/worker/app/export/templates.py` *(new)* — `pack_schema`, `claude_md`, `readme_md`.
- `services/worker/app/export/builder.py` *(new)* — `build_job_archive`.
- `services/worker/app/export/importer.py` *(new)* — `import_result_archive`.
- `services/worker/app/export/jobs.py` *(new)* — `run_build_export`, `run_import_result` (testable cores).
- `services/worker/app/tasks/__init__.py` *(modify)* — `build_export` / `import_result` arq wrappers + register.
- `services/api/app/services/export.py` + `services/api/app/routers/export.py` *(new)* — endpoints; `app/main.py` register; `services/api/pyproject.toml` add `python-multipart`.
- `apps/web/components/snapshot/ExportActions.tsx` *(new, client)* + `InboxRow.tsx`/`[id]/page.tsx` *(modify)* — Export / Download / Upload + `exported` state.

Task order is dependency-driven: data → archive+manifest → templates+builder → importer → jobs+tasks → API → web.

---

### Task 1: `exported` status + `export_dir` + migration

**Files:**
- Modify: `services/shared/gulp_shared/models/source.py`, `services/shared/gulp_shared/settings.py`
- Create (generated): `services/api/alembic/versions/<rev>_s2_exported_status.py`
- Test: `services/shared/tests/test_models.py` (add one)

**Interfaces:**
- Produces: `SnapshotStatus.exported = "exported"`; `settings.export_dir: str` (default `/tmp/gulp-exports`).

- [ ] **Step 1: Write the failing test**

Add to `services/shared/tests/test_models.py`:

```python
def test_snapshot_can_be_exported():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="X",
        status=SnapshotStatus.exported,
    )
    s.add(snap)
    s.commit()
    assert SnapshotStatus.exported.value == "exported"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/shared && uv run pytest tests/test_models.py::test_snapshot_can_be_exported -v`
Expected: FAIL — `AttributeError: exported`

- [ ] **Step 3: Add the enum value + setting**

In `services/shared/gulp_shared/models/source.py`, add `exported` to `SnapshotStatus` (after `ready`):

```python
class SnapshotStatus(str, enum.Enum):
    queued = "queued"
    unprocessed = "unprocessed"
    processing = "processing"
    ready = "ready"
    exported = "exported"
    awaiting_review = "awaiting_review"
    in_library = "in_library"
    needs_attention = "needs_attention"
```

In `services/shared/gulp_shared/settings.py`, add (after `llm_model`):

```python
    export_dir: str = "/tmp/gulp-exports"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/shared && uv run pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Migration**

```bash
just up
cd services/api && uv run --package gulp-api alembic revision -m "s2 exported status" && cd ../..
```

Edit the new revision file: set `down_revision` to the current head (`cb5fcc8902ba`); make `upgrade()` exactly:

```python
def upgrade() -> None:
    op.execute("ALTER TYPE snapshot_status ADD VALUE IF NOT EXISTS 'exported'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE; the enum value is left in place.
    pass
```

Run: `just migrate-up`
Expected: `Running upgrade cb5fcc8902ba -> <rev>`.

- [ ] **Step 6: Commit**

```bash
git add services/shared/gulp_shared/models/source.py services/shared/gulp_shared/settings.py services/shared/tests/test_models.py services/api/alembic/versions/
git commit -m "feat(s2): exported snapshot status + export_dir setting + migration"
```

---

### Task 2: archive primitives (`archive.py` + `manifest.py`)

**Files:**
- Create: `services/worker/app/export/__init__.py`, `services/worker/app/export/archive.py`, `services/worker/app/export/manifest.py`
- Test: `services/worker/tests/test_export_archive.py`

**Interfaces:**
- Produces: `write_zip(files: dict[str, bytes]) -> bytes`; `read_zip(data: bytes, *, max_total: int = 26_214_400) -> dict[str, bytes]` (raises `ValueError` on absolute/`..` entries or when total uncompressed size exceeds `max_total`); `find_entry(files: dict[str, bytes], suffix: str) -> bytes` (the entry whose path == `suffix` or ends with `/`+`suffix`; raises `KeyError`). `FORMAT_VERSION = 1`; `build_manifest(*, snapshot_id, owner_id, input_sha256, created_at) -> dict`; `parse_manifest(data: bytes) -> dict` (raises `ValueError` on bad job_kind / unsupported format_version / missing fields).

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_export_archive.py`:

```python
import json

import pytest

from app.export.archive import find_entry, read_zip, write_zip
from app.export.manifest import FORMAT_VERSION, build_manifest, parse_manifest


def test_write_then_read_round_trips():
    data = write_zip({"a/b.txt": b"hello", "m.json": b"{}"})
    files = read_zip(data)
    assert files["a/b.txt"] == b"hello"
    assert find_entry(files, "b.txt") == b"hello"


def test_read_zip_rejects_zip_slip():
    evil = write_zip({"../escape.txt": b"x"})
    with pytest.raises(ValueError):
        read_zip(evil)


def test_read_zip_rejects_oversize():
    big = write_zip({"big.bin": b"x" * 1000})
    with pytest.raises(ValueError):
        read_zip(big, max_total=10)


def test_manifest_round_trip_and_validation():
    m = build_manifest(snapshot_id="s1", owner_id="o1", input_sha256="abc", created_at="2026-06-26T00:00:00Z")
    assert m["format_version"] == FORMAT_VERSION and m["job_kind"] == "digest"
    parsed = parse_manifest(json.dumps(m).encode())
    assert parsed["snapshot_id"] == "s1"
    with pytest.raises(ValueError):
        parse_manifest(json.dumps({"job_kind": "nope"}).encode())
    with pytest.raises(ValueError):
        parse_manifest(json.dumps({**m, "format_version": 999}).encode())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_export_archive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.export'`

- [ ] **Step 3: Write `archive.py`**

Create `services/worker/app/export/__init__.py`:

```python
"""Export executor: build a downloadable digest job + import its result (S2 design)."""
```

Create `services/worker/app/export/archive.py`:

```python
"""Safe zip read/write for export job + result archives."""

import io
import zipfile
from pathlib import PurePosixPath

_DEFAULT_MAX_TOTAL = 26_214_400  # 25 MiB uncompressed, total


def write_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def read_zip(data: bytes, *, max_total: int = _DEFAULT_MAX_TOTAL) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts:
                raise ValueError(f"unsafe zip entry: {name!r}")
            total += info.file_size
            if total > max_total:
                raise ValueError("archive exceeds size cap")
            out[name] = zf.read(info)
    return out


def find_entry(files: dict[str, bytes], suffix: str) -> bytes:
    for name, content in files.items():
        if name == suffix or name.endswith("/" + suffix):
            return content
    raise KeyError(suffix)
```

- [ ] **Step 4: Write `manifest.py`**

Create `services/worker/app/export/manifest.py`:

```python
"""The job manifest — identity + integrity for a job/result archive."""

import json

FORMAT_VERSION = 1
_REQUIRED = ("format_version", "job_kind", "snapshot_id", "owner_id")


def build_manifest(*, snapshot_id: str, owner_id: str, input_sha256: str, created_at: str) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "job_kind": "digest",
        "snapshot_id": snapshot_id,
        "owner_id": owner_id,
        "input_sha256": input_sha256,
        "created_at": created_at,
    }


def parse_manifest(data: bytes) -> dict:
    try:
        m = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ValueError("manifest is not valid JSON") from exc
    if not isinstance(m, dict) or any(k not in m for k in _REQUIRED):
        raise ValueError("manifest missing required fields")
    if m["job_kind"] != "digest":
        raise ValueError(f"unsupported job_kind {m['job_kind']!r}")
    if m["format_version"] != FORMAT_VERSION:
        raise ValueError(f"unsupported format_version {m['format_version']!r}")
    return m
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_export_archive.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/export/__init__.py services/worker/app/export/archive.py services/worker/app/export/manifest.py services/worker/tests/test_export_archive.py
git commit -m "feat(s2): export archive + manifest primitives (zip-slip safe)"
```

---

### Task 3: `templates.py` + `builder.py`

**Files:**
- Create: `services/worker/app/export/templates.py`, `services/worker/app/export/builder.py`
- Test: `services/worker/tests/test_export_builder.py`

**Interfaces:**
- Consumes: `_SYSTEM` (`app.prompts.digest`), `DigestResult` (`app.pipeline.schemas`), `NormDoc` (`app.pipeline.normdoc`), `write_zip`/`read_zip`/`find_entry` (Task 2), `build_manifest` (Task 2).
- Produces: `pack_schema() -> dict`; `claude_md() -> str`; `readme_md() -> str`; `build_job_archive(*, snapshot_id: str, owner_id: str, normdoc: NormDoc, created_at: str) -> bytes` (assembles README.md, CLAUDE.md, manifest.json, input/norm_doc.json, schema/pack.schema.json, result/HOWTO.txt; `input_sha256` = sha256 of the norm_doc.json bytes).

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_export_builder.py`:

```python
import json

from app.export.archive import find_entry, read_zip
from app.export.builder import build_job_archive
from app.export.templates import claude_md, pack_schema
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(title="A", lang="en", media_type="article", content_body=body,
                   blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))])


def test_pack_schema_and_claude_md():
    schema = pack_schema()
    assert "properties" in schema and "sections" in schema["properties"] and "facets" in schema["properties"]
    cm = claude_md()
    for needle in ("result/pack.json", "input/norm_doc.json", "schema/pack.schema.json", "English"):
        assert needle in cm


def test_build_job_archive_has_all_entries():
    data = build_job_archive(snapshot_id="s1", owner_id="o1", normdoc=_doc(), created_at="2026-06-26T00:00:00Z")
    files = read_zip(data)
    for suffix in ("CLAUDE.md", "README.md", "manifest.json", "input/norm_doc.json",
                   "schema/pack.schema.json", "result/HOWTO.txt"):
        assert find_entry(files, suffix)  # present, non-empty
    nd = json.loads(find_entry(files, "input/norm_doc.json"))
    assert nd["title"] == "A" and nd["blocks"][0]["text"].startswith("Attention")
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["snapshot_id"] == "s1" and man["job_kind"] == "digest"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_export_builder.py -v`
Expected: FAIL — cannot import `app.export.builder`.

- [ ] **Step 3: Write `templates.py`**

Create `services/worker/app/export/templates.py`:

```python
"""Generated archive text — reuses the inline digest prompt (one source of truth)."""

from typing import Any

from app.pipeline.schemas import DigestResult
from app.prompts.digest import _SYSTEM


def pack_schema() -> dict[str, Any]:
    return DigestResult.model_json_schema()


def claude_md() -> str:
    return f"""# Gulp digest job (offline executor)

You are executing one Gulp **digest** job offline — the same task Gulp normally
runs against the Anthropic API. Read `input/norm_doc.json` (a `NormDoc`: title +
`content_body` + structured `blocks`) and write the result as JSON to
`result/pack.json`, matching `schema/pack.schema.json` exactly.

{_SYSTEM}

## Files
- Input:  `input/norm_doc.json`
- Schema: `schema/pack.schema.json`  (your output must validate against this)
- Output: `result/pack.json`         (write your Knowledge Pack here)

When done, validate `result/pack.json` against the schema, then stop. Re-zip this
folder and upload it back into Gulp.
"""


def readme_md() -> str:
    return """# Run this Gulp job in Claude Code

1. `cd` into this folder and launch Claude Code.
2. Say: "Do the Gulp digest job described in CLAUDE.md."
3. When `result/pack.json` is written, re-zip this folder and upload it in Gulp
   (the **Upload result** button on this snapshot).

No API key or network is needed — Claude Code does the reasoning itself.
"""
```

- [ ] **Step 4: Write `builder.py`**

Create `services/worker/app/export/builder.py`:

```python
"""Assemble a downloadable digest job archive from a NormDoc."""

import hashlib
import json

from app.export.archive import write_zip
from app.export.manifest import build_manifest
from app.export.templates import claude_md, pack_schema, readme_md
from app.pipeline.normdoc import NormDoc


def build_job_archive(*, snapshot_id: str, owner_id: str, normdoc: NormDoc, created_at: str) -> bytes:
    norm_doc_bytes = normdoc.model_dump_json(indent=2).encode()
    manifest = build_manifest(
        snapshot_id=snapshot_id,
        owner_id=owner_id,
        input_sha256=hashlib.sha256(norm_doc_bytes).hexdigest(),
        created_at=created_at,
    )
    files = {
        "README.md": readme_md().encode(),
        "CLAUDE.md": claude_md().encode(),
        "manifest.json": json.dumps(manifest, indent=2).encode(),
        "input/norm_doc.json": norm_doc_bytes,
        "schema/pack.schema.json": json.dumps(pack_schema(), indent=2).encode(),
        "result/HOWTO.txt": b"Write pack.json here, matching ../schema/pack.schema.json.\n",
    }
    return write_zip(files)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_export_builder.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/export/templates.py services/worker/app/export/builder.py services/worker/tests/test_export_builder.py
git commit -m "feat(s2): export job builder + CLAUDE.md/schema templates"
```

---

### Task 4: `importer.py`

**Files:**
- Create: `services/worker/app/export/importer.py`
- Test: `services/worker/tests/test_export_importer.py`

**Interfaces:**
- Consumes: `read_zip`/`find_entry` (Task 2), `DigestResult` (`app.pipeline.schemas`).
- Produces: `import_result_archive(data: bytes) -> DigestResult` — safe-unzip → `find_entry(..., "result/pack.json")` → `json.loads` → `DigestResult.model_validate`. Raises `ValueError` (missing/invalid JSON) or `pydantic.ValidationError` (bad shape).

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_export_importer.py`:

```python
import json

import pytest
from pydantic import ValidationError

from app.export.archive import write_zip
from app.export.importer import import_result_archive

_VALID = {
    "summary": "s", "background": None, "confidence": 0.8,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


def test_import_valid_result():
    data = write_zip({"gulp-job-x/result/pack.json": json.dumps(_VALID).encode()})
    out = import_result_archive(data)
    assert out.summary == "s" and out.sections[0].blocks[0].content == "c"


def test_import_missing_pack_raises():
    data = write_zip({"gulp-job-x/manifest.json": b"{}"})
    with pytest.raises(ValueError):
        import_result_archive(data)


def test_import_invalid_shape_raises():
    data = write_zip({"result/pack.json": json.dumps({"summary": "s"}).encode()})  # missing sections/facets
    with pytest.raises(ValidationError):
        import_result_archive(data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_export_importer.py -v`
Expected: FAIL — cannot import `app.export.importer`.

- [ ] **Step 3: Write `importer.py`**

Create `services/worker/app/export/importer.py`:

```python
"""Parse + validate an uploaded result archive into a DigestResult."""

import json

from app.export.archive import find_entry, read_zip
from app.pipeline.schemas import DigestResult


def import_result_archive(data: bytes) -> DigestResult:
    files = read_zip(data)
    try:
        raw = find_entry(files, "result/pack.json")
    except KeyError as exc:
        raise ValueError("archive has no result/pack.json") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("result/pack.json is not valid JSON") from exc
    return DigestResult.model_validate(payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd services/worker && uv run pytest tests/test_export_importer.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/export/importer.py services/worker/tests/test_export_importer.py
git commit -m "feat(s2): export result importer (validate into DigestResult)"
```

---

### Task 5: orchestration cores + arq tasks

**Files:**
- Create: `services/worker/app/export/jobs.py`
- Modify: `services/worker/app/tasks/__init__.py`
- Test: `services/worker/tests/test_export_jobs.py`, `services/worker/tests/test_tasks.py` (add registration asserts)

**Interfaces:**
- Consumes: `_to_normdoc` + `fetch_html` (`app.pipeline.run` / adapters), `build_job_archive` (Task 3), `import_result_archive` (Task 4), `persist_pack` (`app.pipeline.persist`), `SessionLocal`/`Source`/`SnapshotStatus`, `settings.export_dir`.
- Produces: `async def run_build_export(db, source, *, fetch=fetch_html, export_dir=None, now=None) -> str` (fetch+adapt → `build_job_archive` → write `<export_dir>/<id>.zip` → `source.status = exported`; returns the path; on failure → `needs_attention`); `def run_import_result(db, source, data: bytes) -> None` (`import_result_archive` → `persist_pack` → `ready`; on failure → `exported`). Arq wrappers `build_export(ctx, snapshot_id)` and `import_result(ctx, snapshot_id, upload_path)` registered in `WorkerSettings.functions`.

- [ ] **Step 1: Write the failing test**

Create `services/worker/tests/test_export_jobs.py`:

```python
import json
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.export.archive import write_zip
from app.export.jobs import run_build_export, run_import_result
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import KnowledgePack  # type: ignore[import-untyped]
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    MediaType, SnapshotStatus, Source, SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _note(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="My note body.")
    s.add(snap)
    s.flush()
    return snap


async def test_build_export_writes_zip_and_sets_exported(tmp_path):  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    path = await run_build_export(s, snap, export_dir=str(tmp_path), now="2026-06-26T00:00:00Z")
    assert path.endswith(".zip")
    from app.export.archive import find_entry, read_zip
    files = read_zip(open(path, "rb").read())
    assert find_entry(files, "CLAUDE.md")
    assert snap.status == SnapshotStatus.exported


_VALID = {
    "summary": "s", "background": None, "confidence": 0.8,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


def test_import_result_persists_and_sets_ready():  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    snap.status = SnapshotStatus.exported
    s.commit()
    data = write_zip({"result/pack.json": json.dumps(_VALID).encode()})
    run_import_result(s, snap, data)
    assert snap.status == SnapshotStatus.ready
    assert s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)) is not None


def test_import_result_invalid_sets_exported():  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    snap.status = SnapshotStatus.exported
    s.commit()
    run_import_result(s, snap, write_zip({"result/pack.json": b'{"summary":"only"}'}))
    assert snap.status == SnapshotStatus.exported  # rejected, not ready
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd services/worker && uv run pytest tests/test_export_jobs.py -v`
Expected: FAIL — cannot import `app.export.jobs`.

- [ ] **Step 3: Write `jobs.py`**

Create `services/worker/app/export/jobs.py`:

```python
"""Export orchestration cores — testable with injected fetch / export_dir."""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.export.builder import build_job_archive
from app.export.importer import import_result_archive
from app.pipeline.adapters.webpage import fetch_html
from app.pipeline.persist import persist_pack
from app.pipeline.run import _to_normdoc
from gulp_shared.models.source import MediaType, SnapshotStatus, Source  # type: ignore[import-untyped]
from gulp_shared.settings import settings  # type: ignore[import-untyped]

logger = logging.getLogger("gulp.worker")

FetchFn = Callable[[str], Awaitable[str]]


async def run_build_export(
    db: Session,
    source: Source,
    *,
    fetch: FetchFn = fetch_html,
    export_dir: str | None = None,
    now: str | None = None,
) -> str:
    out_dir = export_dir or settings.export_dir
    try:
        normdoc = await _to_normdoc(source, fetch)
        if not normdoc.content_body.strip():
            raise ValueError("extraction produced no content")
        source.content_body = normdoc.content_body
        source.media_type = MediaType(normdoc.media_type)
        data = build_job_archive(
            snapshot_id=str(source.id),
            owner_id=str(source.owner_id),
            normdoc=normdoc,
            created_at=now or datetime.now(UTC).isoformat(),
        )
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{source.id}.zip")
        with open(path, "wb") as f:
            f.write(data)
        source.status = SnapshotStatus.exported
        db.commit()
        return path
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.needs_attention
        db.commit()
        logger.exception("build_export failed for %s", source.id)
        raise


def run_import_result(db: Session, source: Source, data: bytes) -> None:
    try:
        digest = import_result_archive(data)
        persist_pack(db, source, digest)
        source.status = SnapshotStatus.ready
        db.commit()
    except Exception:
        db.rollback()
        source.status = SnapshotStatus.exported
        db.commit()
        logger.exception("import_result failed for %s", source.id)
```

- [ ] **Step 4: Add the arq wrappers**

In `services/worker/app/tasks/__init__.py`, import the cores and add two wrappers + register them. Add to the imports:

```python
from app.export.jobs import run_build_export, run_import_result
```

Add the two job functions (next to `process_snapshot`):

```python
async def build_export(ctx: dict, snapshot_id: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("build_export: snapshot %s not found", snapshot_id)
            return
        await run_build_export(db, source)
    finally:
        db.close()


async def import_result(ctx: dict, snapshot_id: str, upload_path: str) -> None:
    db = SessionLocal()
    try:
        source = db.get(Source, uuid.UUID(snapshot_id))
        if source is None:
            logger.warning("import_result: snapshot %s not found", snapshot_id)
            return
        with open(upload_path, "rb") as f:
            data = f.read()
        run_import_result(db, source, data)
    finally:
        db.close()
```

Update `WorkerSettings.functions`:

```python
    functions = [process_snapshot, build_export, import_result]
```

- [ ] **Step 5: Add the registration assert + run tests**

Add to `services/worker/tests/test_tasks.py`:

```python
def test_export_jobs_registered() -> None:
    from app.tasks import WorkerSettings, build_export, import_result
    assert build_export in WorkerSettings.functions
    assert import_result in WorkerSettings.functions
```

Run: `cd services/worker && uv run pytest tests/test_export_jobs.py tests/test_tasks.py -v`
Expected: PASS. Then the full worker suite: `cd services/worker && uv run pytest -q` — PASS.

- [ ] **Step 6: Commit**

```bash
git add services/worker/app/export/jobs.py services/worker/app/tasks/__init__.py services/worker/tests/test_export_jobs.py services/worker/tests/test_tasks.py
git commit -m "feat(s2): export/import worker jobs (build_export, import_result)"
```

---

### Task 6: API endpoints

**Files:**
- Create: `services/api/app/services/export.py`, `services/api/app/routers/export.py`
- Modify: `services/api/app/main.py`, `services/api/pyproject.toml` (add `python-multipart`)
- Test: `services/api/tests/test_export.py`

**Interfaces:**
- Consumes: `get_db`/`get_current_user`/`get_enqueue`; `Source`/`SnapshotStatus`; `settings.export_dir`.
- Produces: `POST /snapshots/{id}/export` (owner-scoped → `enqueue("build_export", id)` → returns `SnapshotOut`); `GET /snapshots/{id}/job` (owner-scoped → `FileResponse` of `<export_dir>/<id>.zip`, 404 if absent); `POST /snapshots/{id}/import` (owner-scoped; multipart `file`; **shallow stdlib-zipfile check** → on pass stash to `<export_dir>/<id>-result.zip` + `enqueue("import_result", id, path)`; **422** on bad zip / manifest mismatch / missing `result/pack.json`).
- `shallow_check(zip_bytes, snapshot_id, owner_id) -> None` in `app/services/export.py` (raises `ValueError` with a reason).

- [ ] **Step 1: Add the dependency**

In `services/api/pyproject.toml`, add `"python-multipart>=0.0.9"` to `dependencies`. Run `uv sync`.

- [ ] **Step 2: Write the failing test**

Create `services/api/tests/test_export.py`:

```python
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db, get_enqueue
from app.main import app
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    calls: list[tuple[object, ...]] = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def _snap(db, status=SnapshotStatus.unprocessed):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
               status=status, content_body="body")
    db.add(s)
    db.commit()
    return str(s.id)


def _result_zip(snapshot_id: str, *, with_pack=True, owner=str(DEV_USER_ID)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(
            {"format_version": 1, "job_kind": "digest", "snapshot_id": snapshot_id, "owner_id": owner}))
        if with_pack:
            zf.writestr("result/pack.json", json.dumps({"summary": "s", "sections": [], "facets": []}))
    return buf.getvalue()


def test_export_enqueues_build(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db)
    r = client.post(f"/snapshots/{sid}/export")
    assert r.status_code == 200
    assert client.enqueue_calls == [("build_export", sid)]


def test_job_404_when_not_built(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db)
    assert client.get(f"/snapshots/{sid}/job").status_code == 404


def test_import_good_zip_enqueues(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db, status=SnapshotStatus.exported)
    r = client.post(f"/snapshots/{sid}/import",
                    files={"file": ("r.zip", _result_zip(sid), "application/zip")})
    assert r.status_code == 200
    assert any(c[0] == "import_result" and c[1] == sid for c in client.enqueue_calls)


def test_import_missing_pack_422(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db, status=SnapshotStatus.exported)
    r = client.post(f"/snapshots/{sid}/import",
                    files={"file": ("r.zip", _result_zip(sid, with_pack=False), "application/zip")})
    assert r.status_code == 422


def test_import_wrong_snapshot_id_422(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db, status=SnapshotStatus.exported)
    bad = _result_zip("00000000-0000-0000-0000-0000000000ff")
    r = client.post(f"/snapshots/{sid}/import", files={"file": ("r.zip", bad, "application/zip")})
    assert r.status_code == 422
```

- [ ] **Step 3: Write the service**

Create `services/api/app/services/export.py`:

```python
"""Export endpoints' business logic (S2 export executor)."""

import io
import json
import os
import zipfile

from gulp_shared.settings import settings


def job_path(snapshot_id: str) -> str:
    return os.path.join(settings.export_dir, f"{snapshot_id}.zip")


def result_path(snapshot_id: str) -> str:
    return os.path.join(settings.export_dir, f"{snapshot_id}-result.zip")


def _find(zf: zipfile.ZipFile, suffix: str) -> str | None:
    for name in zf.namelist():
        if name == suffix or name.endswith("/" + suffix):
            return name
    return None


def shallow_check(data: bytes, *, snapshot_id: str, owner_id: str) -> None:
    """Stdlib-only sanity check; raises ValueError with a reason on failure."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("upload is not a valid zip") from exc
    man_name = _find(zf, "manifest.json")
    if man_name is None:
        raise ValueError("archive has no manifest.json")
    try:
        man = json.loads(zf.read(man_name))
    except json.JSONDecodeError as exc:
        raise ValueError("manifest.json is not valid JSON") from exc
    if man.get("snapshot_id") != snapshot_id:
        raise ValueError("manifest snapshot_id does not match this snapshot")
    if man.get("owner_id") != owner_id:
        raise ValueError("manifest owner_id does not match")
    if _find(zf, "result/pack.json") is None:
        raise ValueError("archive has no result/pack.json")


def stash_result(data: bytes, snapshot_id: str) -> str:
    os.makedirs(settings.export_dir, exist_ok=True)
    path = result_path(snapshot_id)
    with open(path, "wb") as f:
        f.write(data)
    return path
```

- [ ] **Step 4: Write the router**

Create `services/api/app/routers/export.py`:

```python
"""Export executor endpoints — thin (docs/05 D4)."""

import os
import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import SnapshotOut
from app.services.export import job_path, shallow_check, stash_result
from app.services.snapshots import to_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


def _owned(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.post("/snapshots/{snapshot_id}/export", response_model=SnapshotOut)
def export_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = _owned(db, snapshot_id, user)
    enqueue("build_export", str(source.id))
    return to_out(db, source)


@router.get("/snapshots/{snapshot_id}/job")
def download_job(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _owned(db, snapshot_id, user)
    path = job_path(str(snapshot_id))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="job not built yet")
    return FileResponse(path, media_type="application/zip", filename=f"gulp-job-{str(snapshot_id)[:8]}.zip")


@router.post("/snapshots/{snapshot_id}/import", response_model=SnapshotOut)
def import_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
    file: UploadFile = File(...),
) -> SnapshotOut:
    # MUST be a sync endpoint: `enqueue` uses asyncio.run() internally, which
    # raises inside a running event loop (S1 note). Read via the sync file obj.
    source = _owned(db, snapshot_id, user)
    data = file.file.read()
    try:
        shallow_check(data, snapshot_id=str(source.id), owner_id=str(source.owner_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = stash_result(data, str(source.id))
    enqueue("import_result", str(source.id), path)
    return to_out(db, source)
```

- [ ] **Step 5: Register + run tests**

In `services/api/app/main.py`, add `export` to the import and `app.include_router(export.router, tags=["export"])`.

Run: `cd services/api && uv run pytest tests/test_export.py -v` then `cd services/api && uv run pytest -q`
Expected: PASS (5 export tests + the rest).

- [ ] **Step 6: Regenerate the client + commit**

```bash
just gen-client
git add services/api/app/services/export.py services/api/app/routers/export.py services/api/app/main.py services/api/pyproject.toml services/api/tests/test_export.py packages/api-client/openapi.json packages/api-client/src/schema.gen.ts
git commit -m "feat(s2): export/job/import API endpoints + multipart"
```

---

### Task 7: Web — Export / Download / Upload + `exported` state

**Files:**
- Modify: `packages/api-client/src/index.ts` (helpers), `apps/web/components/inbox/InboxRow.tsx`, `apps/web/app/snapshots/[id]/page.tsx`, `apps/web/lib/pack.ts`
- Create: `apps/web/components/snapshot/ExportActions.tsx`
- Test: `apps/web/lib/pack.test.ts` (extend)

**Interfaces:**
- Consumes: the regenerated client (`POST /export`, `GET /job`, `POST /import`).
- Produces: `@gulp/api-client` helpers `startExport(id)`, `jobDownloadUrl(id)`, `importResult(id, file)`; `ExportActions({ id, status })` client island; `InboxRow`/detail render Export (unprocessed/needs_attention), Download + Upload (exported); `isProcessing` unchanged; a `statusLabel` entry for `exported`.

- [ ] **Step 1: Add client helpers**

In `packages/api-client/src/index.ts`, add:

```typescript
export async function startExport(id: string): Promise<SnapshotOut> {
  const { data, error } = await client.POST("/snapshots/{snapshot_id}/export", {
    params: { path: { snapshot_id: id } },
  });
  if (error || !data) throw new Error("export failed");
  return data;
}

export function jobDownloadUrl(id: string): string {
  return `${baseUrl}/snapshots/${id}/job`;
}

export async function importResult(id: string, file: File): Promise<SnapshotOut> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${baseUrl}/snapshots/${id}/import`, { method: "POST", body });
  if (!res.ok) throw new Error(`import failed (${res.status})`);
  return (await res.json()) as SnapshotOut;
}
```

(`baseUrl` is already defined at the top of the file; export it if needed: change `const baseUrl` to `export const baseUrl`.)

- [ ] **Step 2: Write the failing test (a small logic guard)**

In `apps/web/lib/pack.test.ts`, add:

```typescript
import { statusLabel } from "./pack";

describe("statusLabel", () => {
  it("labels exported and the rest", () => {
    expect(statusLabel("exported")).toBe("Exported");
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("unprocessed")).toBe("Not started");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter @gulp/web exec vitest run lib/pack.test.ts`
Expected: FAIL — `statusLabel` is not exported from `./pack`.

- [ ] **Step 4: Add `statusLabel` to `lib/pack.ts`**

```typescript
import type { Snapshot } from "@gulp/api-client";

export function statusLabel(status: Snapshot["status"]): string {
  if (status === "processing" || status === "queued") return "Processing";
  if (status === "needs_attention") return "Needs attention";
  if (status === "unprocessed") return "Not started";
  if (status === "exported") return "Exported";
  return "Ready";
}
```

(Keep the existing `Snapshot` import if already present — don't duplicate it.)

- [ ] **Step 5: Write `ExportActions` + wire the row**

Create `apps/web/components/snapshot/ExportActions.tsx`:

```tsx
"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { importResult, jobDownloadUrl, startExport } from "@gulp/api-client";
import type { Snapshot } from "@gulp/api-client";
import { Button } from "@/components/ui/Button";

export function ExportActions({ id, status }: { id: string; status: Snapshot["status"] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onExport() {
    setBusy(true);
    try {
      await startExport(id);
    } finally {
      router.refresh();
      setBusy(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      await importResult(id, file);
    } catch (err) {
      alert(String(err)); // v1: surface import errors plainly
    } finally {
      router.refresh();
      setBusy(false);
    }
  }

  if (status === "exported") {
    return (
      <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
        <a href={jobDownloadUrl(id)}><Button variant="secondary">⤓ Download job</Button></a>
        <Button variant="secondary" disabled={busy} onClick={() => fileRef.current?.click()}>⤓ Upload result</Button>
        <input ref={fileRef} type="file" accept=".zip" hidden onChange={onUpload} />
      </span>
    );
  }
  return (
    <Button variant="secondary" disabled={busy} onClick={onExport}>⇪ Export job</Button>
  );
}
```

In `apps/web/components/inbox/InboxRow.tsx`: import `ExportActions` and render it for `unprocessed`/`needs_attention`/`exported` alongside the existing `StartButton`. Replace the action area so an `unprocessed`/`needs_attention` row shows both `StartButton` and `<ExportActions id status>`, and an `exported` row shows `<ExportActions>` (Download + Upload); otherwise the status label. Use `statusLabel(item.status)` from `@/lib/pack` for the label.

- [ ] **Step 6: Wire the detail page**

In `apps/web/app/snapshots/[id]/page.tsx`, add `<ExportActions id={id} status={snap.status} />` into the `unprocessed`, `needs_attention`, and a new `exported` branch (for `exported`, render the ExportActions Download/Upload + the "exported — run it in Claude Code, then upload" copy). Keep the existing branches.

- [ ] **Step 7: Test + build + commit**

Run: `pnpm --filter @gulp/web exec vitest run` (green) and `pnpm --filter @gulp/web build` (the route still builds; no type errors).

```bash
just gen-client  # ensure the client reflects the export endpoints (idempotent if Task 6 ran it)
git add packages/api-client/src/index.ts apps/web/lib/pack.ts apps/web/lib/pack.test.ts apps/web/components/snapshot/ExportActions.tsx apps/web/components/inbox/InboxRow.tsx "apps/web/app/snapshots/[id]/page.tsx"
git commit -m "feat(web): export job download/upload actions + exported state"
```

---

## Self-Review

**Spec coverage** (against the export spec):
- Archive format & contents (CLAUDE.md/README/manifest/input/schema/result) → Tasks 2–3 ✓; `CLAUDE.md` reuses the inline `_SYSTEM` prompt, schema = `DigestResult.model_json_schema()` (single source of truth).
- Worker-prepared build + `exported` status → Tasks 1, 5 ✓.
- Endpoints `POST /export`, `GET /job`, `POST /import` → Task 6 ✓; owner-scoped; shallow stdlib check (no api→worker import).
- Strict two-stage import validation (shallow 422 + deep `model_validate`, zip-slip + size cap, fail → `exported`) → Tasks 2, 4, 5, 6 ✓.
- Module design (archive/manifest/templates/builder/importer pure + testable; jobs thin) → Tasks 2–5 ✓.
- Web Export/Download/Upload + `exported` state → Task 7 ✓.
- **Deferred (per spec §10):** batch, `custom` skill executor, durable storage, sync deep-validation feedback, persisted import-error reason, cards.

**Placeholder scan:** none — every step has concrete code/commands. Task 7 Steps 5–6 describe wiring two existing files with the exact components/props to insert (the new code — `ExportActions`, `statusLabel`, the helpers — is given in full).

**Type consistency:** `write_zip`/`read_zip`/`find_entry`, `build_manifest`/`parse_manifest`, `build_job_archive`, `import_result_archive`, `run_build_export`/`run_import_result`, `build_export`/`import_result`, `shallow_check`/`job_path`/`stash_result`, and the client helpers `startExport`/`jobDownloadUrl`/`importResult` are named identically across their definitions, the worker jobs, the API, the tests, and the web. The job/result paths (`<export_dir>/<id>.zip`, `<id>-result.zip`) match between `jobs.py` (worker write) and `services/export.py` (api read/stash). `DigestResult`/`NormDoc`/`persist_pack`/`_to_normdoc`/`_SYSTEM` are the merged Plan-1/2/3 symbols.
