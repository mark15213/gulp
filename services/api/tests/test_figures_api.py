import uuid

from app.deps import get_db
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.media import figure_abspath
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID

_PNG = b"\x89PNG\r\n\x1a\nx"


def _client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _snap_with_figure(db, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    fig = SourceFigure(source_id=snap.id, order_index=0, label="F1", caption="c",
                       ext="png", mime_type="image/png", width=1, height=1)
    db.add(fig)
    db.commit()
    p = figure_abspath(snap.id, fig.id, "png")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_PNG)
    return snap.id, fig.id


def test_list_figures(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, fid = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1 and body[0]["id"] == str(fid) and body[0]["label"] == "F1"
    app.dependency_overrides.clear()


def test_serve_figure_bytes(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, fid = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures/{fid}")
    assert r.status_code == 200 and r.content == _PNG
    assert r.headers["content-type"].startswith("image/png")
    app.dependency_overrides.clear()


def test_missing_figure_404(db, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sid, _ = _snap_with_figure(db, tmp_path, monkeypatch)
    r = _client(db).get(f"/snapshots/{sid}/figures/{uuid.uuid4()}")
    assert r.status_code == 404
    app.dependency_overrides.clear()
