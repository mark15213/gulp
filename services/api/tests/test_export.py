import io
import json
import zipfile

import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.source import SnapshotStatus, Source, SourceGenre, SourceKind
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
            {"format_version": 1, "job_kind": "digest",
             "snapshot_id": snapshot_id, "owner_id": owner}))
        if with_pack:
            zf.writestr("result/pack.json",
                        json.dumps({"summary": "s", "sections": [], "facets": []}))
    return buf.getvalue()


def test_export_enqueues_build(client, db):  # type: ignore[no-untyped-def]
    sid = _snap(db)
    r = client.post(f"/snapshots/{sid}/export")
    assert r.status_code == 200
    assert client.enqueue_calls == [("build_export", sid)]


def test_export_blocked_for_article_genre(client, db):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="A",
               status=SnapshotStatus.ready, genre=SourceGenre.article,
               content_body="body")
    db.add(s)
    db.commit()
    r = client.post(f"/snapshots/{s.id}/export")
    assert r.status_code == 400
    assert client.enqueue_calls == []


def test_export_allowed_for_paper_genre(client, db):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="P",
               status=SnapshotStatus.ready, genre=SourceGenre.paper,
               content_body="body")
    db.add(s)
    db.commit()
    r = client.post(f"/snapshots/{s.id}/export")
    assert r.status_code == 200


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


def test_job_streams_file(client, db, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    import os

    from app.services import export as export_svc
    monkeypatch.setattr(export_svc.settings, "export_dir", str(tmp_path))
    sid = _snap(db, status=SnapshotStatus.exported)
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(export_svc.job_path(sid), "wb") as f:
        f.write(b"PK\x03\x04 fake zip bytes")
    r = client.get(f"/snapshots/{sid}/job")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


# The web client probes cards-job readiness with an HTTP HEAD (cardsJobReady):
# it must reflect the file's existence (200 vs 404), not 405 Method Not Allowed.
def test_cards_job_head_ready_when_built(client, db, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    import os

    from app.services import export as export_svc
    monkeypatch.setattr(export_svc.settings, "export_dir", str(tmp_path))
    sid = _snap(db, status=SnapshotStatus.ready)
    os.makedirs(str(tmp_path), exist_ok=True)
    with open(export_svc.cards_job_path(sid), "wb") as f:
        f.write(b"PK\x03\x04 fake cards zip")
    r = client.head(f"/snapshots/{sid}/cards/job")
    assert r.status_code == 200


def test_cards_job_head_404_when_not_built(client, db, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    from app.services import export as export_svc
    monkeypatch.setattr(export_svc.settings, "export_dir", str(tmp_path))
    sid = _snap(db, status=SnapshotStatus.ready)
    r = client.head(f"/snapshots/{sid}/cards/job")
    assert r.status_code == 404
