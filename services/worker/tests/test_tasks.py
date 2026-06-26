from typing import Any

import app.tasks as tasks
from app.tasks import WorkerSettings, process_snapshot
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.source import (  # type: ignore[import-untyped]
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class FakeProvider:
    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        return {"summary": "s", "background": None, "confidence": 0.7,
                "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
                "facets": [{"element_type": "claim", "text": "x"}]}


def test_worker_registers_process_snapshot() -> None:
    assert process_snapshot in WorkerSettings.functions


async def test_process_snapshot_loads_and_processes(monkeypatch: Any) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Local()
    seed.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed, media_type=MediaType.note,
                  content_body="body")
    seed.add(snap)
    seed.commit()
    sid = str(snap.id)
    seed.close()

    # process_snapshot opens its own session via SessionLocal, and uses the
    # registered provider — point both at our test doubles.
    monkeypatch.setattr(tasks, "SessionLocal", Local)
    from app.llm import register_provider
    register_provider("anthropic", FakeProvider())

    await process_snapshot({}, sid)

    check = Local()
    got = check.get(Source, snap.id)
    assert got is not None and got.status == SnapshotStatus.ready
    check.close()


async def test_missing_snapshot_is_a_noop(monkeypatch: Any) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(tasks, "SessionLocal", Local)
    await process_snapshot({}, "00000000-0000-0000-0000-0000000000ff")  # no raise


def test_export_jobs_registered() -> None:
    from app.tasks import WorkerSettings, build_export, import_result
    assert build_export in WorkerSettings.functions
    assert import_result in WorkerSettings.functions
