import uuid

import gulp_shared.models  # noqa: F401  (register all tables)
from gulp_shared.db import Base
from gulp_shared.media import figure_abspath, figure_relpath, media_root
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_source_figure_row_roundtrips() -> None:
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T", status=SnapshotStatus.ready
    )
    s.add(snap)
    s.flush()
    fig = SourceFigure(
        source_id=snap.id,
        order_index=0,
        label="Figure 1",
        caption="A cat.",
        ext="png",
        mime_type="image/png",
        width=640,
        height=480,
    )
    s.add(fig)
    s.commit()
    got = s.scalar(select(SourceFigure).where(SourceFigure.source_id == snap.id))
    assert got is not None and got.label == "Figure 1" and got.ext == "png"


def test_media_path_helpers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", "/data/media")
    sid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    fid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    assert figure_relpath(sid, fid, "png") == f"{sid}/{fid}.png"
    assert figure_abspath(sid, fid, "png") == media_root() / str(sid) / f"{fid}.png"
