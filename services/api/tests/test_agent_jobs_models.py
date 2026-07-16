from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models import (
    AgentJob,
    AgentJobKind,
    AgentJobState,
    ApiToken,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID


def _snap(db):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
               status=SnapshotStatus.unprocessed, content_body="body")
    db.add(s)
    db.commit()
    return s


def test_agent_job_defaults(db):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = AgentJob(owner_id=DEV_USER_ID, snapshot_id=s.id, kind=AgentJobKind.digest)
    db.add(job)
    db.commit()
    assert job.state is AgentJobState.building
    assert job.attempts == 0
    assert job.lease_expires_at is None and job.completed_at is None


def test_latest_job_skips_failed(db):  # type: ignore[no-untyped-def]
    s = _snap(db)
    failed = AgentJob(owner_id=DEV_USER_ID, snapshot_id=s.id,
                      kind=AgentJobKind.digest, state=AgentJobState.failed)
    db.add(failed)
    db.commit()
    assert latest_job(db, s.id, AgentJobKind.digest) is None
    live = AgentJob(owner_id=DEV_USER_ID, snapshot_id=s.id, kind=AgentJobKind.digest)
    db.add(live)
    db.commit()
    assert latest_job(db, s.id, AgentJobKind.digest) == live
    # other kind unaffected
    assert latest_job(db, s.id, AgentJobKind.cards) is None


def test_api_token_defaults(db):  # type: ignore[no-untyped-def]
    t = ApiToken(user_id=DEV_USER_ID, name="laptop", token_hash="h" * 64, prefix="gulp_pat_abc")
    db.add(t)
    db.commit()
    assert t.scope == "agent"
    assert t.revoked_at is None and t.last_used_at is None
