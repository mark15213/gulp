# S2 Export Executor — design

*Gulp · feature design · 2026-06-26 · brainstorm output*

> The deferred **`export` executor** from the S2 design (`docs/subsystems/S2-processing-design.md` C4/§2.4/§9). An `unprocessed` snapshot's digest job can be **downloaded as a `.zip`**, run by the user inside **Claude Code** (or any agent), and the result **uploaded back** — populating the same `KnowledgePack` the inline path would, with no Anthropic API call. Motive: run a backlog on a CC/Codex subscription instead of metered API.

## 1. Why an agent can run the archive directly

The digest is a *pure* task — `content in → structured pack out` — fully specified by three things and nothing else: an **instruction** (the prompt), an **input** (the already-fetched `NormDoc`), and an **output contract** (the `DigestResult` JSON Schema). Claude Code is itself a Claude agent that reads and writes files, so a folder holding `instruction + input + schema + an empty result slot` is natively executable — no Gulp code, no API key, no network. The cheap deterministic half (fetch + parse → `NormDoc`) already ran on Gulp's server; only the *understanding* half is exported. This is exactly the `job-spec ↔ executor` seam frozen to disk.

## 2. Scope

- **In:** single-job export — a worker-built `.zip` per `unprocessed` snapshot; a new `exported` status; download + upload (import) endpoints + worker jobs; the `CLAUDE.md`/`README.md`/schema/manifest archive; strict import validation reusing `persist_pack`; Inbox/detail **⤓ Export** + **⤓ Upload result** actions.
- **Out (deferred):** batch (one archive for many jobs); the `custom` (user-skill) executor; durable/multi-host archive storage (v1 uses a local export dir); synchronous deep-validation feedback on upload (v1 does a shallow sync check + async deep validation); cards (only the report-digest job is exported, matching the inline v1).

## 3. The archive — format & contents

A **`.zip`** (cross-platform, matches the user's "压缩包" mental model). It unzips to a self-contained, agent-runnable folder:

```
gulp-job-<id8>.zip
└─ gulp-job-<id8>/
   ├─ README.md            # human-facing: what this is + the exact line to paste into Claude Code + re-zip/upload steps
   ├─ CLAUDE.md            # the task itself (CC auto-loads it) — the inline digest prompt, re-pointed at file I/O
   ├─ manifest.json        # { format_version:1, job_kind:"digest", snapshot_id, owner_id, gulp_commit, created_at, input_sha256 }
   ├─ input/
   │  └─ norm_doc.json     # the NormDoc: { title, lang, media_type, content_body, blocks:[{text, section_label?, anchor}] }
   ├─ schema/
   │  └─ pack.schema.json  # DigestResult.model_json_schema() — the output contract
   └─ result/
      └─ HOWTO.txt         # "write pack.json in this folder, matching ../schema/pack.schema.json"
```

Each piece: `CLAUDE.md` = what to do · `input/norm_doc.json` = the data (fetch+parse already done server-side) · `schema/pack.schema.json` = the contract the agent self-validates against · `result/` = where the answer goes · `manifest.json` = identity + integrity for import.

### `CLAUDE.md` (the runnable core)
Generated from the **inline digest prompt** (`services/worker/app/prompts/digest.py`) — one source of truth — re-pointed at files:

```markdown
# Gulp digest job (offline executor)
Read `input/norm_doc.json`, produce a Knowledge Pack (a re-authored, faithful
study report + facets), and write it as JSON to `result/pack.json` matching
`schema/pack.schema.json` exactly.
- Write everything in English, regardless of source language.
- Re-author into clear prose — do NOT copy verbatim, and NEVER invent facts the
  source doesn't support. If the source is thin, say less.
- sections[] of {heading?, blocks:[{type: prose|callout|quote, content}]};
  facets[] of {element_type: key_term|person_org|claim|counter_view|connection, text};
  confidence in [0,1] (lower for thin/partial sources).
When done, validate result/pack.json against the schema, stop, then re-zip this folder and upload it into Gulp.
```

`README.md` repeats the steps for a human (cd in, launch CC, say "go", re-zip, upload).

## 4. Flow & status machine

```
unprocessed --⤓ Export--> (worker build_export: fetch+adapt → NormDoc → assemble files → zip → stash) --> exported
   [UI polls; on `exported` shows ⤓ Download job]
exported --⤓ Download--> user runs it in Claude Code --> result/pack.json
exported --⤓ Upload result--> (API shallow-check → worker import_result: unzip → validate vs schema → persist_pack) --> ready
   (invalid result → back to `exported` + an error message surfaced in the UI)
```

- **New `Snapshot.status` value `exported`** (added to the enum + migration `ALTER TYPE snapshot_status ADD VALUE 'exported'`; `02 §6` state machine updated). Transitions: `unprocessed → exported` (build done), `exported → ready` (import ok), `exported → exported` (re-export / failed import). `exported` is still **startable** (the inline ▶ Start remains available as an alternative) and re-exportable.
- During the build the snapshot stays `unprocessed`; the client optimistically shows "preparing export…" and polls until `exported`. (No separate "building" status.)

## 5. Endpoints

- `POST /snapshots/{id}/export` — owner-scoped; enqueues a worker `build_export(snapshot_id)` job; returns the snapshot (the UI polls until `exported`).
- `GET /snapshots/{id}/job` — owner-scoped; streams the stashed `.zip` (`Content-Disposition: attachment; filename="gulp-job-<id8>.zip"`); 404 if not yet built.
- `POST /snapshots/{id}/import` — owner-scoped; accepts the uploaded `.zip` (multipart). **Shallow sync checks** (valid zip; `manifest.json` parses; `manifest.snapshot_id == {id}` and `owner_id == caller`; `result/pack.json` exists and is valid JSON) → reject obvious errors with **422**. On pass, stash the upload and enqueue `import_result(snapshot_id, path)`; return the snapshot.

## 6. Import: validation, persistence, security

The worker `import_result` job:
1. **Unzip safely** — reject any entry with an absolute path or `..` (zip-slip); cap total uncompressed size.
2. **Deep-validate** `result/pack.json` against `pack.schema.json` (jsonschema), then parse into `DigestResult` (`model_validate`).
3. **Idempotent persist** — `persist_pack(db, source, digest)` (the exact Plan-3 function: drops any existing pack, rebuilds rows) → `source.status = ready`.
4. On any failure → `source.status = exported` and the worker **logs** the reason; the UI shows a generic "import failed — check the result and re-upload." (Surfacing the *specific* reason via a persisted field is a future nicety, §10.)

`manifest.input_sha256` lets the worker confirm the result was produced for this job's input (mismatch → warn, not block).

## 7. Storage & reuse

- **Archive storage:** a local **export dir** (`settings.export_dir`, default `/tmp/gulp-exports`), keyed `<snapshot_id>.zip`. Single-host, non-durable — acceptable for v1 (mirrors the deferred blob store). The api and worker share this filesystem (same host).
- **Reuse (all worker-side):** `NormDoc` + adapters + `fetch_html` (build), the digest **prompt** (CLAUDE.md body), `DigestResult` + its `model_json_schema()` (schema file + validation), `persist_pack` (import). The API stays thin: enqueue + serve/receive files + the shallow checks.

## 8. Testing

- **Builder (worker):** given a seeded snapshot, `build_export` produces a zip with all expected entries; `manifest` fields correct; `pack.schema.json` == `DigestResult.model_json_schema()`; `norm_doc.json` round-trips into a `NormDoc`. (note path is hermetic; link path uses an injected fetch.)
- **Import (worker):** a hand-built result zip with a valid `pack.json` → `persist_pack` writes the rows + `ready`; a zip whose `pack.json` fails the schema → status `exported` + error; a zip-slip entry → rejected.
- **API:** `POST /export` enqueues; `GET /job` 404 before build, streams after; `POST /import` shallow-rejects a bad zip (422), enqueues a good one; all owner-scoped (foreign → 404).
- **Web:** the Inbox/detail `exported` state renders Download + Upload; the export poller; (logic unit-tested, interactive eyeballed).

## 9. Decomposition (plans)

1. **Plan E1 — export/build/download:** the `exported` status + migration; the worker `build_export` job + archive builder (NormDoc → files → zip, CLAUDE.md/README/schema/manifest); `POST /export` + `GET /job`; the web ⤓ Export action + `exported` state + poll-to-download.
2. **Plan E2 — import:** `POST /import` (shallow checks) + the worker `import_result` job (safe unzip, schema-validate, `persist_pack`, status + error handling); the web ⤓ Upload result action.

## 10. Open / deferred

- **Batch** export (one archive, many jobs) — the format already isolates a job under its own folder, so batch is a `jobs/<id>/…` wrapper later.
- **`custom` executor** (a user-authored CC skill `/gulp-digest`) — the ergonomic repeat-use path once the format is proven.
- **Durable / multi-host archive storage** (blob store) — replaces the local export dir when the blob layer lands.
- **Synchronous deep-validation feedback** on upload (vs the v1 shallow-sync + async-deep split) — when `DigestResult`/schema are reachable from the API.
- **Persisting the specific import-failure reason** (a `Source` column) so the UI can show it, rather than the v1 generic message.
- **Cards** in the exported job — when card generation lands, the job carries both schemas.
