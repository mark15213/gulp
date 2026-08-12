"""Agent-jobs channel logic (spec 2026-07-16). This module is the API-side
brain of the MCP channel; the MCP tools in app/mcp are thin wrappers over it."""

import io
import json
import os
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jsonschema
from gulp_shared.contracts import archive_entries as ae
from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models.agent_job import AgentJob, AgentJobKind, AgentJobState
from gulp_shared.models.source import SnapshotStatus, Source, SourceGenre, SourceKind
from gulp_shared.models.user import User
from pydantic import ValidationError
from sqlalchemy import CursorResult, and_, or_, select, update
from sqlalchemy.orm import Session

from app.services.export import cards_job_path, job_path, stash_result

LEASE_MINUTES = 30
MAX_ERRORS = 20

REBUILD_AFTER_S = 30
# The states in which a queue row is still the channel's business: not built
# yet, claimable, or leased. Such a row is re-published in place; `done`/`failed`
# rows are terminal history and a re-publish earns a fresh row.
_LIVE = (AgentJobState.building, AgentJobState.pending, AgentJobState.leased)
_REBUILD_TASK = {AgentJobKind.digest: "build_export", AgentJobKind.cards: "build_cards_export"}
# Statuses `publish_job` accepts. `needs_attention` is a deliberate retry path
# (a failed in-app read is exactly what an agent might rescue); `ready` and the
# in-flight pair belong to whoever already owns the snapshot.
_PUBLISHABLE = (SnapshotStatus.unprocessed, SnapshotStatus.needs_attention)


def publish(db: Session, source: Source, kind: AgentJobKind) -> AgentJob:
    """Called by the Export actions: create or reset the queue row. The worker
    flips building→pending once the archive is stashed."""
    job = latest_job(db, source.id, kind)
    if job is not None and job.state in _LIVE:
        job.state = AgentJobState.building
        job.attempts = 0
        job.last_error = None
        job.lease_expires_at = None
    else:
        job = AgentJob(owner_id=source.owner_id, snapshot_id=source.id, kind=kind)
        db.add(job)
    db.commit()
    return job


class AgentJobUnavailable(Exception):
    """Protocol-level rejection surfaced to the MCP client as a structured error."""

    def __init__(self, code: str, message: str, retry_after_s: int | None = None) -> None:
        self.code = code
        self.message = message
        self.retry_after_s = retry_after_s
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(UTC)


def _lease_expired(job: AgentJob) -> bool:
    exp = job.lease_expires_at
    if exp is None:
        return True
    if exp.tzinfo is None:  # sqlite in tests returns naive datetimes
        exp = exp.replace(tzinfo=UTC)
    return exp <= _now()


def _get_owned(db: Session, user: User, job_id: str) -> AgentJob:
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise AgentJobUnavailable("not_found", "job not found") from None
    job = db.get(AgentJob, jid)
    if job is None or job.owner_id != user.id:
        raise AgentJobUnavailable("not_found", "job not found")
    return job


def _parse_kind(kind: str | None) -> AgentJobKind | None:
    if kind is None:
        return None
    try:
        return AgentJobKind(kind)
    except ValueError:
        raise AgentJobUnavailable(
            "invalid_kind", 'kind must be "digest" or "cards"'
        ) from None


def _candidates(db: Session, user: User) -> list[dict[str, Any]]:
    """Snapshots the owner captured and never routed anywhere — no queue row, no
    in-app pipeline run. They are not jobs yet: `publish_job` makes them one.

    Deliberately narrower than what `publish_job` accepts: `needs_attention` is
    publishable on request but never auto-listed, so a snapshot whose archive
    build keeps failing cannot put a drain loop into a spin."""
    live_row = (
        select(AgentJob.id)
        .where(AgentJob.snapshot_id == Source.id, AgentJob.state.in_(_LIVE))
        .exists()
    )
    stmt = (
        select(Source)
        .where(
            Source.owner_id == user.id,
            Source.kind == SourceKind.snapshot,
            Source.deleted_at.is_(None),
            Source.status == SnapshotStatus.unprocessed,
            # Same gate as the Export action: a digest job is an LLM deep-read,
            # which only makes sense for papers. Unclassified stays eligible.
            or_(Source.genre.is_(None), Source.genre == SourceGenre.paper),
            ~live_row,
        )
        .order_by(Source.created_at)
    )
    return [
        {
            "job_id": None,  # there is no row yet — publish_job(snapshot_id) makes one
            "kind": AgentJobKind.digest.value,
            "title": source.title,
            "snapshot_id": str(source.id),
            "state": "unpublished",
            "attempts": 0,
            "created_at": source.created_at.isoformat(),
        }
        for source in db.scalars(stmt)
    ]


def list_jobs(
    db: Session, user: User, kind: str | None = None, include_candidates: bool = False
) -> list[dict[str, Any]]:
    kind_enum = _parse_kind(kind)
    stmt = (
        select(AgentJob, Source.title)
        .join(Source, Source.id == AgentJob.snapshot_id)
        .where(AgentJob.owner_id == user.id, AgentJob.state.in_(_LIVE))
        .order_by(AgentJob.created_at)
    )
    if kind_enum is not None:
        stmt = stmt.where(AgentJob.kind == kind_enum)
    out: list[dict[str, Any]] = []
    for job, title in db.execute(stmt):
        state = job.state
        if state is AgentJobState.leased:
            if not _lease_expired(job):
                continue  # someone is working on it
            state = AgentJobState.pending  # expired lease → claimable again
        out.append(
            {
                "job_id": str(job.id),
                "kind": job.kind.value,
                "title": title,
                "snapshot_id": str(job.snapshot_id),
                "state": state.value,
                "attempts": job.attempts,
                "created_at": job.created_at.isoformat(),
            }
        )
    # Published work first, discovery second — the drain loop should finish what
    # it already owns before it decides to take on more. Cards jobs are published
    # by the cards flow (a pack must exist first), so they have no candidates.
    if include_candidates and kind_enum is not AgentJobKind.cards:
        out.extend(_candidates(db, user))
    return out


def publish_job(
    db: Session, user: User, snapshot_id: str, enqueue: Callable[..., None]
) -> dict[str, Any]:
    """The agent channel's own entry point — the web Export action's twin, so a
    capture can reach the queue without a browser round-trip. Idempotent: a
    snapshot that already has a live row gets that row back, not a second one."""
    try:
        sid = uuid.UUID(snapshot_id)
    except ValueError:
        raise AgentJobUnavailable("not_found", "snapshot not found") from None
    source = db.get(Source, sid)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise AgentJobUnavailable("not_found", "snapshot not found")
    existing = latest_job(db, source.id, AgentJobKind.digest)
    if existing is not None and existing.state in _LIVE:
        return _published(existing, source)
    if source.genre is not None and source.genre is not SourceGenre.paper:
        raise AgentJobUnavailable(
            "not_applicable",
            f"digest jobs only apply to paper sources (this one is {source.genre.value})",
        )
    if source.status not in _PUBLISHABLE:
        raise AgentJobUnavailable(
            "not_publishable",
            f"snapshot is {source.status.value} — nothing to hand to the agent channel",
        )
    job = publish(db, source, AgentJobKind.digest)
    enqueue("build_export", str(source.id))
    return _published(job, source)


def _published(job: AgentJob, source: Source) -> dict[str, Any]:
    out: dict[str, Any] = {
        "job_id": str(job.id),
        "kind": job.kind.value,
        "title": source.title,
        "snapshot_id": str(source.id),
        "state": job.state.value,
    }
    if job.state is AgentJobState.building:
        # The worker is packaging the archive; claim_job would reject until it lands.
        out["retry_after_s"] = REBUILD_AFTER_S
    return out


def _read_archive(snapshot_id: str, kind: AgentJobKind) -> dict[str, Any] | None:
    """Zip entries → claim payload parts; None = missing/stale archive (rebuild).
    The zip is the single source of truth — nothing here re-generates content."""
    path = job_path(snapshot_id) if kind is AgentJobKind.digest else cards_job_path(snapshot_id)
    if not os.path.exists(path):
        return None
    with zipfile.ZipFile(path) as zf:
        def read(suffix: str) -> bytes | None:
            for name in zf.namelist():  # entries may sit under a folder prefix
                if name == suffix or name.endswith("/" + suffix):
                    return zf.read(name)
            return None

        instruction = read(ae.INSTRUCTIONS_MCP)
        manifest = read(ae.MANIFEST)
        if instruction is None or manifest is None:
            return None  # pre-MCP archive → stale
        if kind is AgentJobKind.digest:
            norm = read(ae.INPUT_NORM_DOC)
            schema = read(ae.SCHEMA_PACK)
            if norm is None or schema is None:
                return None
            payload_input: Any = json.loads(norm)
        else:
            pack = read(ae.INPUT_PACK)
            schema = read(ae.SCHEMA_CARDS)
            if pack is None or schema is None:
                return None
            conv = read(ae.INPUT_CONVERSATION)
            payload_input = {
                "pack_md": pack.decode(),
                "conversation_md": conv.decode() if conv is not None else None,
            }
        return {
            "instruction": instruction.decode(),
            "input": payload_input,
            "output_schema": json.loads(schema),
            "manifest_raw": manifest,
        }


def _claimable_conditions(job_id: uuid.UUID, now: datetime) -> tuple[Any, ...]:
    """WHERE conditions for the atomic lease UPDATE (spec §3): only a `pending`
    row, or a `leased` row whose lease has already expired, is claimable. This is
    what excludes done/failed/building and unexpired-leased rows *inside* the
    UPDATE, so two agents racing on the same row can't both lease it. New states
    that should be claimable must be added here."""
    return (
        AgentJob.id == job_id,
        or_(
            AgentJob.state == AgentJobState.pending,
            and_(
                AgentJob.state == AgentJobState.leased,
                AgentJob.lease_expires_at < now,
            ),
        ),
    )


def _rebuild(db: Session, job: AgentJob, enqueue: Callable[..., None]) -> AgentJobUnavailable:
    job.state = AgentJobState.building
    job.lease_expires_at = None
    db.commit()
    enqueue(_REBUILD_TASK[job.kind], str(job.snapshot_id))
    return AgentJobUnavailable(
        "rebuilding",
        "job archive is being rebuilt — retry shortly",
        retry_after_s=REBUILD_AFTER_S,
    )


def claim_job(
    db: Session, user: User, job_id: str, enqueue: Callable[..., None]
) -> dict[str, Any]:
    job = _get_owned(db, user, job_id)
    if job.state in (AgentJobState.done, AgentJobState.failed):
        raise AgentJobUnavailable("not_claimable", f"job is {job.state.value}")
    if job.state is AgentJobState.building:
        raise AgentJobUnavailable(
            "building", "job archive not built yet", retry_after_s=REBUILD_AFTER_S
        )
    if job.state is AgentJobState.leased and not _lease_expired(job):
        raise AgentJobUnavailable(
            "leased", f"job is leased until {job.lease_expires_at.isoformat()}"  # type: ignore[union-attr]
        )
    payload = _read_archive(str(job.snapshot_id), job.kind)
    if payload is None:
        raise _rebuild(db, job, enqueue)
    # Atomic lease acquisition: re-check claimability inside the UPDATE's WHERE so
    # a concurrent claim between the reads above and here can't double-lease. A
    # rowcount of 0 means another agent won the row → surface the "leased" error.
    now = _now()
    new_expiry = now + timedelta(minutes=LEASE_MINUTES)
    result = cast(
        "CursorResult[Any]",
        db.execute(
            update(AgentJob)
            .where(*_claimable_conditions(job.id, now))
            .values(state=AgentJobState.leased, lease_expires_at=new_expiry)
            .execution_options(synchronize_session=False),
        ),
    )
    if result.rowcount == 0:
        db.rollback()
        raise AgentJobUnavailable("leased", "job was just claimed by another agent")
    db.commit()
    return {
        "job_id": str(job.id),
        "kind": job.kind.value,
        "instruction": payload["instruction"],
        "input": payload["input"],
        "output_schema": payload["output_schema"],
        "lease_expires_at": new_expiry.isoformat(),
    }


def _reject(db: Session, job: AgentJob, errors: list[dict[str, str]]) -> dict[str, Any]:
    job.attempts += 1
    job.state = AgentJobState.pending
    job.lease_expires_at = None
    db.commit()
    return {"accepted": False, "errors": errors[:MAX_ERRORS]}


def _supersede(db: Session, job: AgentJob, why: str) -> AgentJobUnavailable:
    job.state = AgentJobState.failed
    job.last_error = f"superseded: {why}"
    db.commit()
    return AgentJobUnavailable("superseded", f"job superseded — {why}")


def submit_result(
    db: Session, user: User, job_id: str, result: dict[str, Any], enqueue: Callable[..., None]
) -> dict[str, Any]:
    job = _get_owned(db, user, job_id)
    if job.state is AgentJobState.done:
        return {"accepted": True, "already_completed": True}
    if job.state is AgentJobState.building:
        raise AgentJobUnavailable(
            "building", "job archive not built yet", retry_after_s=REBUILD_AFTER_S
        )
    if job.state is AgentJobState.failed:
        raise AgentJobUnavailable("failed", "job failed — re-publish it from the web UI")
    source = db.get(Source, job.snapshot_id)
    if source is None or source.deleted_at is not None:
        raise _supersede(db, job, "snapshot is gone")
    if job.kind is AgentJobKind.digest:
        if source.status is not SnapshotStatus.exported:
            raise _supersede(db, job, "snapshot was processed by another path")
        payload = _read_archive(str(job.snapshot_id), job.kind)
        if payload is None:
            raise _rebuild(db, job, enqueue)
        validator = jsonschema.Draft202012Validator(payload["output_schema"])
        errors = [
            {"path": "/".join(str(p) for p in e.absolute_path), "message": e.message}
            for e in validator.iter_errors(result)
        ]
        if errors:
            return _reject(db, job, errors)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", payload["manifest_raw"])
            zf.writestr("result/pack.json", json.dumps(result))
        path = stash_result(buf.getvalue(), str(source.id))
        enqueue("import_result", str(source.id), path)
        job.state = AgentJobState.done  # worker reverts to pending if deep validation fails
        job.completed_at = _now()
        job.lease_expires_at = None
        db.commit()
        return {"accepted": True}
    # cards: validation and persistence are both synchronous. There is deliberately
    # no supersede check here (unlike digest): cards are additive, so a job stays
    # valid regardless of snapshot status — only a gone snapshot (checked above)
    # supersedes it.
    try:
        payload_model = CardsPayload.model_validate(result)
    except ValidationError as exc:
        errors = [
            {"path": "/".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _reject(db, job, errors)
    # Local import: cards.py imports `publish` from this module, so a top-level
    # import here would be a circular import (breaks app startup).
    from app.services.cards import import_cards

    import_cards(db, source, payload_model)
    job.state = AgentJobState.done
    job.completed_at = _now()
    job.lease_expires_at = None
    db.commit()
    return {"accepted": True, "cards": len(payload_model.cards)}


def report_failure(db: Session, user: User, job_id: str, reason: str) -> dict[str, Any]:
    job = _get_owned(db, user, job_id)
    if job.state is AgentJobState.done:
        return {"ok": False, "note": "already completed"}
    job.state = AgentJobState.failed
    job.last_error = reason[:2000]
    job.lease_expires_at = None
    db.commit()
    return {"ok": True}
