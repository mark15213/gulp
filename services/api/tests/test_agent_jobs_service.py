import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from app.services import agent_jobs as svc
from app.services.agent_jobs import AgentJobUnavailable
from gulp_shared.contracts import archive_entries as ae
from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models import (
    AgentJob,
    AgentJobKind,
    AgentJobState,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID
from gulp_shared.settings import settings

PACK_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}


@pytest.fixture(autouse=True)
def _export_dir(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "export_dir", str(tmp_path))


@pytest.fixture
def enqueue_calls():  # type: ignore[no-untyped-def]
    calls: list[tuple[object, ...]] = []
    return calls


@pytest.fixture
def enqueue(enqueue_calls):  # type: ignore[no-untyped-def]
    return lambda *a: enqueue_calls.append(a)


def _snap(db, status=SnapshotStatus.exported):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="Paper T",
               status=status, content_body="body")
    db.add(s)
    db.commit()
    return s


def _job(db, source, kind=AgentJobKind.digest, state=AgentJobState.pending, **kw):  # type: ignore[no-untyped-def]
    job = AgentJob(owner_id=source.owner_id, snapshot_id=source.id,
                   kind=kind, state=state, **kw)
    db.add(job)
    db.commit()
    return job


def _write_digest_zip(source):  # type: ignore[no-untyped-def]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(ae.INSTRUCTIONS_MCP, "# job\ndo the thing")
        zf.writestr(ae.MANIFEST, json.dumps(
            {"format_version": 1, "job_kind": "digest",
             "snapshot_id": str(source.id), "owner_id": str(source.owner_id)}))
        zf.writestr(ae.INPUT_NORM_DOC, json.dumps({"title": "T", "content_body": "b"}))
        zf.writestr(ae.SCHEMA_PACK, json.dumps(PACK_SCHEMA))
    import os
    os.makedirs(settings.export_dir, exist_ok=True)
    with open(f"{settings.export_dir}/{source.id}.zip", "wb") as f:
        f.write(buf.getvalue())


def _write_cards_zip(source, with_conversation=True):  # type: ignore[no-untyped-def]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(ae.INSTRUCTIONS_MCP, "# cards job")
        zf.writestr(ae.MANIFEST, json.dumps(
            {"format_version": 1, "job_kind": "cards",
             "snapshot_id": str(source.id), "owner_id": str(source.owner_id)}))
        zf.writestr(ae.INPUT_PACK, "# pack")
        if with_conversation:
            zf.writestr(ae.INPUT_CONVERSATION, "q&a")
        zf.writestr(ae.SCHEMA_CARDS, json.dumps({"type": "object"}))
    import os
    os.makedirs(settings.export_dir, exist_ok=True)
    with open(f"{settings.export_dir}/{source.id}-cards.zip", "wb") as f:
        f.write(buf.getvalue())


# --- list_jobs ---

def test_list_shows_pending_and_building_hides_done_leased(db, owner):  # type: ignore[no-untyped-def]
    s = _snap(db)
    _job(db, s, state=AgentJobState.pending)
    s2 = _snap(db)
    _job(db, s2, state=AgentJobState.building)
    s3 = _snap(db)
    _job(db, s3, state=AgentJobState.done)
    s4 = _snap(db)
    _job(db, s4, state=AgentJobState.leased,
         lease_expires_at=datetime.now(UTC) + timedelta(minutes=10))
    jobs = svc.list_jobs(db, owner)
    states = {j["snapshot_id"]: j["state"] for j in jobs}
    assert states == {str(s.id): "pending", str(s2.id): "building"}


def test_list_expired_lease_shows_as_pending(db, owner):  # type: ignore[no-untyped-def]
    s = _snap(db)
    _job(db, s, state=AgentJobState.leased,
         lease_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    jobs = svc.list_jobs(db, owner)
    assert len(jobs) == 1 and jobs[0]["state"] == "pending"


def test_list_kind_filter(db, owner):  # type: ignore[no-untyped-def]
    s = _snap(db)
    _job(db, s, kind=AgentJobKind.digest)
    _job(db, s, kind=AgentJobKind.cards)
    assert {j["kind"] for j in svc.list_jobs(db, owner, "cards")} == {"cards"}


# --- claim_job ---

def test_claim_returns_payload_and_leases(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s)
    _write_digest_zip(s)
    out = svc.claim_job(db, owner, str(job.id), enqueue)
    assert out["kind"] == "digest"
    assert out["instruction"].startswith("# job")
    assert out["input"]["title"] == "T"
    assert out["output_schema"] == PACK_SCHEMA
    db.refresh(job)
    assert job.state is AgentJobState.leased and job.lease_expires_at is not None


def test_claim_cards_payload(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db, status=SnapshotStatus.ready)
    job = _job(db, s, kind=AgentJobKind.cards)
    _write_cards_zip(s)
    out = svc.claim_job(db, owner, str(job.id), enqueue)
    assert out["input"] == {"pack_md": "# pack", "conversation_md": "q&a"}


def test_claim_missing_zip_triggers_rebuild(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s)
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(job.id), enqueue)
    assert exc.value.code == "rebuilding" and exc.value.retry_after_s == 30
    assert enqueue_calls == [("build_export", str(s.id))]
    db.refresh(job)
    assert job.state is AgentJobState.building


def test_claim_stale_zip_without_mcp_entry_rebuilds(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s)
    import os
    os.makedirs(settings.export_dir, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", "{}")
    with open(f"{settings.export_dir}/{s.id}.zip", "wb") as f:
        f.write(buf.getvalue())
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(job.id), enqueue)
    assert exc.value.code == "rebuilding"


def test_claim_conflicts(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db)
    leased = _job(db, s, state=AgentJobState.leased,
                  lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(leased.id), enqueue)
    assert exc.value.code == "leased"
    building = _job(db, _snap(db), state=AgentJobState.building)
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(building.id), enqueue)
    assert exc.value.code == "building"
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(uuid.uuid4()), enqueue)
    assert exc.value.code == "not_found"


def test_claim_expired_lease_reclaims(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    _write_digest_zip(s)
    out = svc.claim_job(db, owner, str(job.id), enqueue)
    assert out["job_id"] == str(job.id)


def test_claim_foreign_job_not_found(db, owner, enqueue):  # type: ignore[no-untyped-def]
    from gulp_shared.models.user import User
    other = User(display_name="other")
    db.add(other)
    db.commit()
    s = Source(owner_id=other.id, kind=SourceKind.snapshot, title="X",
               status=SnapshotStatus.exported, content_body="b")
    db.add(s)
    db.commit()
    job = AgentJob(owner_id=other.id, snapshot_id=s.id, kind=AgentJobKind.digest,
                   state=AgentJobState.pending)
    db.add(job)
    db.commit()
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(job.id), enqueue)
    assert exc.value.code == "not_found"


def test_claim_race_second_claim_raises_leased(db, owner, enqueue):  # type: ignore[no-untyped-def]
    # As far as sqlite lets us simulate the race: the first claim leases the row,
    # a second claim on the now-leased row is rejected.
    s = _snap(db)
    job = _job(db, s)
    _write_digest_zip(s)
    first = svc.claim_job(db, owner, str(job.id), enqueue)
    assert first["job_id"] == str(job.id)
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.claim_job(db, owner, str(job.id), enqueue)
    assert exc.value.code == "leased"


def test_claimable_where_excludes_terminal_and_held(db, owner):  # type: ignore[no-untyped-def]
    # Direct check that the atomic UPDATE's WHERE only matches a pending row or an
    # expired-lease row — never done/failed/building or an unexpired lease.
    from sqlalchemy import update
    now = datetime.now(UTC)
    future = now + timedelta(minutes=10)
    past = now - timedelta(minutes=10)
    pending = _job(db, _snap(db), state=AgentJobState.pending)
    building = _job(db, _snap(db), state=AgentJobState.building)
    done = _job(db, _snap(db), state=AgentJobState.done)
    failed = _job(db, _snap(db), state=AgentJobState.failed)
    held = _job(db, _snap(db), state=AgentJobState.leased, lease_expires_at=future)
    expired = _job(db, _snap(db), state=AgentJobState.leased, lease_expires_at=past)

    def _matches(job):  # type: ignore[no-untyped-def]
        r = db.execute(
            update(AgentJob)
            .where(*svc._claimable_conditions(job.id, now))
            .values(state=AgentJobState.leased, lease_expires_at=future)
            .execution_options(synchronize_session=False)
        )
        db.rollback()  # we only care whether the WHERE matched
        return r.rowcount

    assert _matches(pending) == 1
    assert _matches(expired) == 1
    assert _matches(building) == 0
    assert _matches(done) == 0
    assert _matches(failed) == 0
    assert _matches(held) == 0


def test_list_jobs_invalid_kind_raises(db, owner):  # type: ignore[no-untyped-def]
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.list_jobs(db, owner, "bogus")
    assert exc.value.code == "invalid_kind"


# --- submit_result ---

def test_submit_digest_valid(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    _write_digest_zip(s)
    out = svc.submit_result(db, owner, str(job.id), {"summary": "fine"}, enqueue)
    assert out == {"accepted": True}
    db.refresh(job)
    assert job.state is AgentJobState.done and job.completed_at is not None
    assert enqueue_calls[0][0] == "import_result"
    # the stashed result zip passes the existing shallow_check
    from app.services.export import result_path, shallow_check
    with open(result_path(str(s.id)), "rb") as f:
        shallow_check(f.read(), snapshot_id=str(s.id), owner_id=str(s.owner_id))


def test_submit_digest_schema_reject(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    _write_digest_zip(s)
    out = svc.submit_result(db, owner, str(job.id), {"nope": 1}, enqueue)
    assert out["accepted"] is False
    assert out["errors"] and "summary" in json.dumps(out["errors"])
    db.refresh(job)
    assert job.state is AgentJobState.pending and job.attempts == 1
    assert enqueue_calls == []


def test_submit_cards_valid(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db, status=SnapshotStatus.ready)
    job = _job(db, s, kind=AgentJobKind.cards, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    result = {"cards": [{"card_type": "flashcard", "prompt": "q", "answer": "a"}]}
    out = svc.submit_result(db, owner, str(job.id), result, enqueue)
    assert out == {"accepted": True, "cards": 1}
    from gulp_shared.models import Card
    assert db.query(Card).filter_by(source_id=s.id).count() == 1
    db.refresh(job)
    assert job.state is AgentJobState.done


def test_submit_cards_invalid(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db, status=SnapshotStatus.ready)
    job = _job(db, s, kind=AgentJobKind.cards, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    out = svc.submit_result(db, owner, str(job.id), {"cards": []}, enqueue)
    assert out["accepted"] is False and out["errors"]
    db.refresh(job)
    assert job.attempts == 1 and job.state is AgentJobState.pending


def test_submit_done_job_is_idempotent(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s, state=AgentJobState.done)
    out = svc.submit_result(db, owner, str(job.id), {"summary": "x"}, enqueue)
    assert out["accepted"] is True and out["already_completed"] is True


def test_submit_superseded_when_snapshot_moved_on(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db, status=SnapshotStatus.ready)  # inline Start already produced a pack
    job = _job(db, s, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.submit_result(db, owner, str(job.id), {"summary": "x"}, enqueue)
    assert exc.value.code == "superseded"
    db.refresh(job)
    assert job.state is AgentJobState.failed


# --- report_failure ---

def test_report_failure(db, owner):  # type: ignore[no-untyped-def]
    s = _snap(db)
    job = _job(db, s, state=AgentJobState.leased,
               lease_expires_at=datetime.now(UTC) + timedelta(minutes=5))
    out = svc.report_failure(db, owner, str(job.id), "model kept hallucinating")
    assert out == {"ok": True}
    db.refresh(job)
    assert job.state is AgentJobState.failed
    assert job.last_error == "model kept hallucinating"


# --- publish_job + candidates (spec 2026-07-16 §3; agent-side publish) ---

def _capture(db, **kw):  # type: ignore[no-untyped-def]
    """A snapshot as `POST /capture` leaves it: kept, unread, unrouted."""
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="Fresh paper",
               status=SnapshotStatus.unprocessed, **kw)
    db.add(s)
    db.commit()
    return s


def test_candidates_are_opt_in(db, owner):  # type: ignore[no-untyped-def]
    _capture(db)
    assert svc.list_jobs(db, owner) == []
    rows = svc.list_jobs(db, owner, include_candidates=True)
    assert len(rows) == 1
    assert rows[0]["state"] == "unpublished" and rows[0]["job_id"] is None
    assert rows[0]["kind"] == "digest"


def test_candidates_exclude_snapshots_that_already_have_a_live_job(db, owner):  # type: ignore[no-untyped-def]
    s = _capture(db)
    _job(db, s, state=AgentJobState.pending)
    rows = svc.list_jobs(db, owner, include_candidates=True)
    assert [r["state"] for r in rows] == ["pending"]  # the job, not a duplicate candidate


def test_candidates_exclude_non_paper_and_already_routed(db, owner):  # type: ignore[no-untyped-def]
    from gulp_shared.models.source import SourceGenre
    _capture(db, genre=SourceGenre.article)  # zero-LLM genre — no digest to outsource
    _snap(db, status=SnapshotStatus.ready)  # already has a pack
    _snap(db, status=SnapshotStatus.processing)  # the in-app pipeline owns it
    _snap(db, status=SnapshotStatus.needs_attention)  # publishable on request, never auto-listed
    deleted = _capture(db)
    deleted.deleted_at = datetime.now(UTC)
    db.commit()
    assert svc.list_jobs(db, owner, include_candidates=True) == []


def test_candidates_are_owner_scoped(db, owner):  # type: ignore[no-untyped-def]
    from gulp_shared.models.user import User
    other = User(display_name="other")
    db.add(other)
    db.commit()
    db.add(Source(owner_id=other.id, kind=SourceKind.snapshot, title="Theirs",
                  status=SnapshotStatus.unprocessed))
    db.commit()
    assert svc.list_jobs(db, owner, include_candidates=True) == []


def test_candidates_absent_for_cards_kind(db, owner):  # type: ignore[no-untyped-def]
    _capture(db)
    assert svc.list_jobs(db, owner, "cards", include_candidates=True) == []
    assert len(svc.list_jobs(db, owner, "digest", include_candidates=True)) == 1


def test_publish_job_builds_and_enqueues(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    s = _capture(db)
    out = svc.publish_job(db, owner, str(s.id), enqueue)
    assert out["state"] == "building"
    assert out["retry_after_s"] == svc.REBUILD_AFTER_S
    assert out["snapshot_id"] == str(s.id) and out["title"] == "Fresh paper"
    assert enqueue_calls == [("build_export", str(s.id))]
    job = latest_job(db, s.id, AgentJobKind.digest)
    assert job is not None and str(job.id) == out["job_id"]


def test_publish_job_is_idempotent(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    s = _capture(db)
    first = svc.publish_job(db, owner, str(s.id), enqueue)
    second = svc.publish_job(db, owner, str(s.id), enqueue)
    assert first["job_id"] == second["job_id"]
    assert len(enqueue_calls) == 1  # the second call did not re-queue the build


def test_publish_job_returns_a_pending_job_untouched(db, owner, enqueue, enqueue_calls):  # type: ignore[no-untyped-def]
    """A built job is claimable — re-publishing must not knock it back to building."""
    s = _capture(db)
    job = _job(db, s, state=AgentJobState.pending)
    out = svc.publish_job(db, owner, str(s.id), enqueue)
    assert out["job_id"] == str(job.id) and out["state"] == "pending"
    assert "retry_after_s" not in out
    assert enqueue_calls == []
    db.refresh(job)
    assert job.state is AgentJobState.pending


def test_publish_job_rejects_non_paper_genre(db, owner, enqueue):  # type: ignore[no-untyped-def]
    from gulp_shared.models.source import SourceGenre
    s = _capture(db, genre=SourceGenre.note)
    with pytest.raises(AgentJobUnavailable) as exc:
        svc.publish_job(db, owner, str(s.id), enqueue)
    assert exc.value.code == "not_applicable"


def test_publish_job_rejects_a_snapshot_someone_else_owns_the_flow_of(db, owner, enqueue):  # type: ignore[no-untyped-def]
    for status in (SnapshotStatus.ready, SnapshotStatus.processing, SnapshotStatus.queued):
        s = _snap(db, status=status)
        with pytest.raises(AgentJobUnavailable) as exc:
            svc.publish_job(db, owner, str(s.id), enqueue)
        assert exc.value.code == "not_publishable", status


def test_publish_job_accepts_needs_attention_as_a_retry(db, owner, enqueue):  # type: ignore[no-untyped-def]
    s = _snap(db, status=SnapshotStatus.needs_attention)
    assert svc.publish_job(db, owner, str(s.id), enqueue)["state"] == "building"


def test_publish_job_foreign_or_missing_snapshot_not_found(db, owner, enqueue):  # type: ignore[no-untyped-def]
    from gulp_shared.models.user import User
    other = User(display_name="other")
    db.add(other)
    db.commit()
    theirs = Source(owner_id=other.id, kind=SourceKind.snapshot, title="Theirs",
                    status=SnapshotStatus.unprocessed)
    db.add(theirs)
    db.commit()
    for bad in (str(uuid.uuid4()), "not-a-uuid", str(theirs.id)):
        with pytest.raises(AgentJobUnavailable) as exc:
            svc.publish_job(db, owner, bad, enqueue)
        assert exc.value.code == "not_found", bad
