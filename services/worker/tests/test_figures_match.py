# services/worker/tests/test_figures_match.py
import gulp_shared.models  # noqa: F401
from app.pipeline.figures.match import fig_number, group_logical, link_figures
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snap(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready, media_type=MediaType.pdf,
                  origin_url="https://arxiv.org/abs/2606.17162")
    s.add(snap)
    s.flush()
    return snap


def _figure(s, snap, order, label=None, caption=None):  # type: ignore[no-untyped-def]
    row = SourceFigure(source_id=snap.id, order_index=order, label=label,
                       caption=caption, ext="png", mime_type="image/png")
    s.add(row)
    s.flush()
    return row


def _figure_blocks(s, snap, labels, preset=None):  # type: ignore[no-untyped-def]
    """Pack with one section holding a figure block per label. `preset` maps
    block index -> pre-existing figure_id."""
    pack = KnowledgePack(snapshot_id=snap.id, title="T", pack_type=PackType.paper,
                         extras={"key_insight": "k"}, status=PackStatus.ready)
    s.add(pack)
    s.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    s.add(sec)
    s.flush()
    blocks = []
    for i, label in enumerate(labels):
        data = {"label": label, "explanation": "e",
                "figure_id": (preset or {}).get(i)}
        b = PackBlock(section_id=sec.id, block_type=PackBlockType.figure,
                      data=data, position=i)
        s.add(b)
        blocks.append(b)
    s.flush()
    return blocks


def test_fig_number_parses_common_label_shapes() -> None:
    assert fig_number("Figure 3") == 3
    assert fig_number("Fig. 12: overview") == 12
    assert fig_number("figure 2 — attention maps") == 2
    assert fig_number("FIGURE 4") == 4
    assert fig_number("Table 1") is None
    assert fig_number("Architecture") is None
    assert fig_number("") is None


def test_group_logical_collapses_subfigure_runs() -> None:
    def fig(order, label, caption):  # type: ignore[no-untyped-def]
        return SourceFigure(order_index=order, label=label, caption=caption,
                            ext="png", mime_type="image/png")

    rows = [
        fig(0, "fig:a", "First."),
        fig(1, "fig:a", "First."),   # subfigure of the same env
        fig(2, "fig:b", "Second."),
        fig(3, None, None),           # captionless env is its own figure
        fig(4, None, None),           # ...and so is the next one
    ]
    logical = group_logical(rows)
    assert [f.order_index for f in logical] == [0, 2, 3, 4]


def test_group_logical_returns_empty_for_fallback_scan() -> None:
    rows = [
        SourceFigure(order_index=i, label=None, caption=None,
                     ext="png", mime_type="image/png")
        for i in range(3)
    ]
    assert group_logical(rows) == []


def test_link_figures_links_by_number() -> None:
    s = _session()
    snap = _snap(s)
    f1 = _figure(s, snap, 0, label="fig:a", caption="First.")
    f2 = _figure(s, snap, 1, label="fig:b", caption="Second.")
    b_two, b_one = _figure_blocks(s, snap, ["Figure 2", "Figure 1"])
    assert link_figures(s, snap) == 2
    assert b_two.data["figure_id"] == str(f2.id)
    assert b_one.data["figure_id"] == str(f1.id)


def test_link_figures_counts_subfigure_group_as_one() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, label="fig:a", caption="Same.")
    _figure(s, snap, 1, label="fig:a", caption="Same.")
    other = _figure(s, snap, 2, label="fig:b", caption="Other.")
    (block,) = _figure_blocks(s, snap, ["Figure 2"])
    assert link_figures(s, snap) == 1
    assert block.data["figure_id"] == str(other.id)


def test_link_figures_skips_fallback_figures() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0)  # no label, no caption
    (block,) = _figure_blocks(s, snap, ["Figure 1"])
    assert link_figures(s, snap) == 0
    assert block.data["figure_id"] is None


def test_link_figures_never_overwrites_existing_link() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, caption="First.")
    (block,) = _figure_blocks(s, snap, ["Figure 1"], preset={0: "manually-chosen"})
    assert link_figures(s, snap) == 0
    assert block.data["figure_id"] == "manually-chosen"


def test_link_figures_skips_out_of_range_and_unparseable() -> None:
    s = _session()
    snap = _snap(s)
    _figure(s, snap, 0, caption="Only one.")
    b_nine, b_none = _figure_blocks(s, snap, ["Figure 9", "Overview diagram"])
    assert link_figures(s, snap) == 0
    assert b_nine.data["figure_id"] is None
    assert b_none.data["figure_id"] is None


def test_link_figures_without_figures_or_pack_is_zero() -> None:
    s = _session()
    snap = _snap(s)
    assert link_figures(s, snap) == 0  # no figures at all
    _figure(s, snap, 0, caption="C.")
    assert link_figures(s, snap) == 0  # figures but no pack
