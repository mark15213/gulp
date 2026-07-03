import gulp_shared.models  # noqa: F401
from app.pipeline.figures.persist import persist_figures
from app.pipeline.figures.types import ExtractedFigure
from gulp_shared.db import Base
from gulp_shared.media import figure_abspath
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    s.add(snap)
    s.flush()
    return snap


def _fig(order: int) -> ExtractedFigure:
    return ExtractedFigure(data=b"\x89PNG\r\n\x1a\nx", ext="png", mime="image/png",
                           label=f"Figure {order}", caption="c", order=order,
                           width=10, height=10)


def test_persist_writes_files_and_rows(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    rows = persist_figures(s, snap, [_fig(0), _fig(1)])
    s.commit()
    assert len(rows) == 2
    for r in rows:
        assert figure_abspath(snap.id, r.id, r.ext).read_bytes().startswith(b"\x89PNG")
    assert len(list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))) == 2


def test_persist_is_idempotent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    persist_figures(s, snap, [_fig(0), _fig(1)])
    s.commit()
    persist_figures(s, snap, [_fig(0)])  # replace
    s.commit()
    rows = list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))
    assert len(rows) == 1
