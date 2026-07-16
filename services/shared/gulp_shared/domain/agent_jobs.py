"""Queue-row lookup shared by the API (publish/claim/submit) and the worker
(build/import state flips)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gulp_shared.models.agent_job import AgentJob, AgentJobKind, AgentJobState


def latest_job(db: Session, snapshot_id: uuid.UUID, kind: AgentJobKind) -> AgentJob | None:
    """Newest non-`failed` row for (snapshot, kind) — the row the channel acts on.
    `failed` rows are terminal history; a re-publish creates a fresh row."""
    return db.scalars(
        select(AgentJob)
        .where(
            AgentJob.snapshot_id == snapshot_id,
            AgentJob.kind == kind,
            AgentJob.state != AgentJobState.failed,
        )
        .order_by(AgentJob.created_at.desc())
    ).first()
