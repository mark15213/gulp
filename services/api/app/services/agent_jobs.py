"""Agent-jobs channel logic (spec 2026-07-16). This module is the API-side
brain of the MCP channel; the MCP tools in app/mcp are thin wrappers over it."""

import io
import json
import os
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jsonschema
from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models.agent_job import AgentJob, AgentJobKind, AgentJobState
from gulp_shared.models.source import SnapshotStatus, Source
from gulp_shared.models.user import User
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.export import cards_job_path, job_path, stash_result

LEASE_MINUTES = 30
MAX_ERRORS = 20

_RESETTABLE = (AgentJobState.building, AgentJobState.pending, AgentJobState.leased)
_REBUILD_TASK = {AgentJobKind.digest: "build_export", AgentJobKind.cards: "build_cards_export"}


def publish(db: Session, source: Source, kind: AgentJobKind) -> AgentJob:
    """Called by the Export actions: create or reset the queue row. The worker
    flips building→pending once the archive is stashed."""
    job = latest_job(db, source.id, kind)
    if job is not None and job.state in _RESETTABLE:
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


def list_jobs(db: Session, user: User, kind: str | None = None) -> list[dict[str, Any]]:
    stmt = (
        select(AgentJob, Source.title)
        .join(Source, Source.id == AgentJob.snapshot_id)
        .where(
            AgentJob.owner_id == user.id,
            AgentJob.state.in_(
                [AgentJobState.building, AgentJobState.pending, AgentJobState.leased]
            ),
        )
        .order_by(AgentJob.created_at)
    )
    if kind is not None:
        stmt = stmt.where(AgentJob.kind == AgentJobKind(kind))
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

        instruction = read("instructions.mcp.md")
        manifest = read("manifest.json")
        if instruction is None or manifest is None:
            return None  # pre-MCP archive → stale
        if kind is AgentJobKind.digest:
            norm = read("input/norm_doc.json")
            schema = read("schema/pack.schema.json")
            if norm is None or schema is None:
                return None
            payload_input: Any = json.loads(norm)
        else:
            pack = read("input/pack.md")
            schema = read("schema/cards.schema.json")
            if pack is None or schema is None:
                return None
            conv = read("input/conversation.md")
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


def _rebuild(db: Session, job: AgentJob, enqueue: Callable[..., None]) -> AgentJobUnavailable:
    job.state = AgentJobState.building
    job.lease_expires_at = None
    db.commit()
    enqueue(_REBUILD_TASK[job.kind], str(job.snapshot_id))
    return AgentJobUnavailable(
        "rebuilding", "job archive is being rebuilt — retry shortly", retry_after_s=30
    )


def claim_job(
    db: Session, user: User, job_id: str, enqueue: Callable[..., None]
) -> dict[str, Any]:
    job = _get_owned(db, user, job_id)
    if job.state in (AgentJobState.done, AgentJobState.failed):
        raise AgentJobUnavailable("not_claimable", f"job is {job.state.value}")
    if job.state is AgentJobState.building:
        raise AgentJobUnavailable("building", "job archive not built yet", retry_after_s=30)
    if job.state is AgentJobState.leased and not _lease_expired(job):
        raise AgentJobUnavailable(
            "leased", f"job is leased until {job.lease_expires_at.isoformat()}"  # type: ignore[union-attr]
        )
    payload = _read_archive(str(job.snapshot_id), job.kind)
    if payload is None:
        raise _rebuild(db, job, enqueue)
    job.state = AgentJobState.leased
    job.lease_expires_at = _now() + timedelta(minutes=LEASE_MINUTES)
    db.commit()
    return {
        "job_id": str(job.id),
        "kind": job.kind.value,
        "instruction": payload["instruction"],
        "input": payload["input"],
        "output_schema": payload["output_schema"],
        "lease_expires_at": job.lease_expires_at.isoformat(),
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
        raise AgentJobUnavailable("building", "job archive not built yet", retry_after_s=30)
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
    # cards: validation and persistence are both synchronous
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
