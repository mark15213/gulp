# services/worker/tests/test_figures_link.py
"""Post-import auto-link: extract figures if missing, then match to blocks."""
import gzip
import io
import tarfile

import gulp_shared.models  # noqa: F401
from app.pipeline.adapters.fetch import FetchedDoc
from app.pipeline.figures.run import link_imported_figures
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.source import MediaType, SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_PNG = b"\x89PNG\r\n\x1a\n" + b"rest"
_TEX = (b"\\begin{figure}\\includegraphics{a.png}"
        b"\\caption{Overview.}\\label{fig:o}\\end{figure}")


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s, url="https://arxiv.org/abs/2606.17162"):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf,
                  origin_url=url)
    s.add(snap)
    s.flush()
    return snap


def _pack_with_figure_block(s, snap):  # type: ignore[no-untyped-def]
    pack = KnowledgePack(snapshot_id=snap.id, title="T", pack_type=PackType.paper,
                         extras={"key_insight": "k"}, status=PackStatus.ready)
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    s.add(sec)
    s.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.figure,
                      data={"label": "Figure 1", "explanation": "e", "figure_id": None},
                      position=0)
    s.add(block)
    s.flush()
    return block


def _targz(files):  # type: ignore[no-untyped-def]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue())


async def test_extracts_then_links(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    block = _pack_with_figure_block(s, snap)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        return FetchedDoc(content=_targz({"m.tex": _TEX, "a.png": _PNG}),
                          content_type="application/gzip")

    await link_imported_figures(s, snap, fetch)
    fig = s.scalar(select(SourceFigure).where(SourceFigure.source_id == snap.id))
    assert fig is not None
    assert block.data["figure_id"] == str(fig.id)


async def test_skips_fetch_when_figures_exist(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s)
    block = _pack_with_figure_block(s, snap)
    fig = SourceFigure(source_id=snap.id, order_index=0, label="fig:o",
                       caption="Overview.", ext="png", mime_type="image/png")
    s.add(fig)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch when figures already exist")

    await link_imported_figures(s, snap, fetch)
    assert block.data["figure_id"] == str(fig.id)


async def test_non_arxiv_is_noop(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("gulp_shared.settings.settings.media_dir", str(tmp_path))
    s = _session()
    snap = _snap(s, url="https://example.com/paper")
    block = _pack_with_figure_block(s, snap)
    s.commit()

    async def fetch(url):  # type: ignore[no-untyped-def]
        raise AssertionError("must not fetch non-arxiv sources")

    await link_imported_figures(s, snap, fetch)
    assert block.data["figure_id"] is None
