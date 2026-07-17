import json

import gulp_shared.models  # noqa: F401
import pytest
from app.export.archive import find_entry, read_zip, write_zip
from app.export.jobs import (
    run_build_cards_export,
    run_build_export,
    run_import_result,
)
from gulp_shared.db import Base
from gulp_shared.domain.agent_jobs import latest_job
from gulp_shared.models import AgentJob, AgentJobKind, AgentJobState
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.source import (
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


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


def _ready_pack(s, snap):  # type: ignore[no-untyped-def]
    pack = KnowledgePack(
        snapshot_id=snap.id, title="BERT", pack_type=PackType.paper,
        extras={"key_insight": "bidirectional", "core_contributions": ["MLM"]},
        status=PackStatus.ready,
    )
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="Approach", position=0)
    s.add(sec)
    s.flush()
    s.add(
        PackBlock(
            section_id=sec.id, block_type=PackBlockType.prose,
            data={"content": "Masked language modeling."}, position=0,
        )
    )
    s.flush()
    return pack


def test_build_cards_export_writes_zip(tmp_path):  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    _ready_pack(s, snap)
    s.commit()
    path = run_build_cards_export(
        s, snap, export_dir=str(tmp_path), now="2026-07-03T00:00:00Z"
    )
    assert path.endswith("-cards.zip")
    files = read_zip(open(path, "rb").read())
    assert find_entry(files, "CLAUDE.md")
    assert b"BERT" in find_entry(files, "input/pack.md")
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["job_kind"] == "cards" and man["snapshot_id"] == str(snap.id)


def test_build_cards_export_without_ready_pack_raises(tmp_path):  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)  # no pack
    s.commit()
    with pytest.raises(ValueError):
        run_build_cards_export(s, snap, export_dir=str(tmp_path))


_VALID = {
    "title": "T",
    "core_contributions": ["c"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
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


def _empty_note(s):  # type: ignore[no-untyped-def]
    """Like `_note`, but with an empty body — no origin_url means `_to_normdoc`
    takes the note path and raises "extraction produced no content"."""
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="")
    s.add(snap)
    s.flush()
    return snap


def _job(db, source, kind=AgentJobKind.digest, state=AgentJobState.building):  # type: ignore[no-untyped-def]
    job = AgentJob(owner_id=source.owner_id, snapshot_id=source.id, kind=kind, state=state)
    db.add(job)
    db.commit()
    return job


async def test_build_export_flips_job_to_pending(tmp_path):  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    job = _job(s, snap)
    await run_build_export(s, snap, export_dir=str(tmp_path), now="2026-06-26T00:00:00Z")
    s.refresh(job)
    assert job.state is AgentJobState.pending


async def test_build_export_failure_marks_job_failed(tmp_path):  # type: ignore[no-untyped-def]
    s = _session()
    snap = _empty_note(s)
    job = _job(s, snap)
    with pytest.raises(ValueError):
        await run_build_export(s, snap, export_dir=str(tmp_path))
    s.refresh(job)
    assert job.state is AgentJobState.failed
    assert job.last_error


def test_import_result_completes_job():  # type: ignore[no-untyped-def]
    s = _session()
    snap = _note(s)
    snap.status = SnapshotStatus.exported
    s.commit()
    job = _job(s, snap, state=AgentJobState.pending)
    data = write_zip({"result/pack.json": json.dumps(_VALID).encode()})
    run_import_result(s, snap, data)
    s.refresh(job)
    assert job.state is AgentJobState.done
    assert job.completed_at is not None


def test_import_result_failure_reverts_done_job():  # type: ignore[no-untyped-def]
    # the MCP submit path marks done before the async deep validation runs
    s = _session()
    snap = _note(s)
    snap.status = SnapshotStatus.exported
    s.commit()
    job = _job(s, snap, state=AgentJobState.done)
    run_import_result(s, snap, write_zip({"result/pack.json": b'{"summary":"only"}'}))
    s.refresh(job)
    assert job.state is AgentJobState.pending
    assert job.attempts == 1
    assert "import failed" in job.last_error


def test_import_result_without_job_row_still_works():  # type: ignore[no-untyped-def]
    # the pre-MCP manual flow: no agent_job row exists; import must not crash
    s = _session()
    snap = _note(s)
    snap.status = SnapshotStatus.exported
    s.commit()
    data = write_zip({"result/pack.json": json.dumps(_VALID).encode()})
    run_import_result(s, snap, data)
    assert snap.status == SnapshotStatus.ready
    assert latest_job(s, snap.id, AgentJobKind.digest) is None
