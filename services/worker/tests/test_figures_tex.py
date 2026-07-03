# services/worker/tests/test_figures_tex.py
from app.pipeline.figures.tex import parse_graphicspath, parse_tex_refs


def test_ordered_refs_with_caption_and_label() -> None:
    tex = r"""
    \begin{figure}
      \includegraphics[width=1\linewidth]{figures/arch}
      \caption{The architecture.}\label{fig:arch}
    \end{figure}
    Text \includegraphics{plot.png} inline.
    """
    refs = parse_tex_refs(tex)
    assert [r.path for r in refs] == ["figures/arch", "plot.png"]
    assert refs[0].caption == "The architecture." and refs[0].label == "fig:arch"
    assert refs[1].caption is None
    assert [r.order for r in refs] == [0, 1]


def test_comments_are_ignored() -> None:
    tex = "% \\includegraphics{ignored.png}\n\\includegraphics{real.png}\n"
    assert [r.path for r in parse_tex_refs(tex)] == ["real.png"]


def test_graphicspath() -> None:
    assert parse_graphicspath(r"\graphicspath{{figs/}{img/}}") == ["figs/", "img/"]
    assert parse_graphicspath("no graphicspath here") == []
