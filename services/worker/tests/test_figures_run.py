# services/worker/tests/test_figures_run.py
import gzip
import io
import tarfile

import gulp_shared.models  # noqa: F401
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.run import extract_arxiv_figures
from gulp_shared.db import Base
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s, url):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf, origin_url=url)
    s.add(snap)
    s.flush()
    return snap


def _targz(files):  # type: ignore[no-untyped-def]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


async def test_extracts_for_arxiv_url(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, "https://arxiv.org/pdf/2606.17162")

    async def fetch(url):  # type: ignore[no-untyped-def]
        assert url == "https://arxiv.org/e-print/2606.17162"
        return FetchedDoc(content=_targz({"m.tex": b"\\includegraphics{a.png}", "a.png": _PNG}),
                          content_type="application/gzip")

    await extract_arxiv_figures(s, snap, fetch)
    assert len(list(s.scalars(select(SourceFigure).where(SourceFigure.source_id == snap.id)))) == 1


async def test_non_arxiv_is_noop(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, "https://example.com/paper.pdf")

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch for non-arxiv")

    await extract_arxiv_figures(s, snap, fetch)
    assert list(s.scalars(select(SourceFigure))) == []


async def test_pipeline_swallows_figure_errors(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    from app.pipeline.run import _maybe_extract_figures
    s = _session()
    snap = _snap(s, "https://arxiv.org/pdf/2606.17162")

    async def boom(url):  # type: ignore[no-untyped-def]
        raise RuntimeError("network down")

    await _maybe_extract_figures(s, snap, boom)   # must not raise
    assert snap.status == SnapshotStatus.ready
