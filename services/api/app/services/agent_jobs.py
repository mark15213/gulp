"""Agent-jobs channel logic (spec 2026-07-16). This module is the API-side
brain of the MCP channel; the MCP tools in app/mcp are thin wrappers over it."""

from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models.agent_job import AgentJob, AgentJobKind, AgentJobState
from gulp_shared.models.source import Source
from sqlalchemy.orm import Session

_RESETTABLE = (AgentJobState.building, AgentJobState.pending, AgentJobState.leased)


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
