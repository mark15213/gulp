import pytest
from app.pipeline.schemas import (
    FigureBlock,
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
    TableBlock,
    draft_from_paper_report,
)
from pydantic import ValidationError


def _report() -> PaperReport:
    return PaperReport(
        title="BERT",
        core_contributions=["MLM enables deep bidirectionality."],
        key_insight="Change the objective, not the architecture.",
        sections=[
            Section(
                heading="The Core Challenge",
                blocks=[
                    ProseBlock(content="The **problem** and why it matters."),
                    FormulaBlock(latex="L=-\\sum_i y_i\\log p_i", explanation="Cross-entropy."),
                    TableBlock(headers=["Model", "F1"], rows=[["BERT", "93.2"]], caption="Results"),
                ],
            )
        ],
        references=[
            Reference(citation="Vaswani et al. (2017)", why_interesting="The Transformer.")
        ],
    )


def test_paper_report_round_trips() -> None:
    r = _report()
    again = PaperReport.model_validate_json(r.model_dump_json())
    assert again == r
    assert again.sections[0].blocks[0].type == "prose"
    assert again.sections[0].blocks[1].latex.startswith("L=")


def test_blocks_are_discriminated_by_type() -> None:
    r = PaperReport.model_validate(
        {
            "title": "T",
            "core_contributions": ["c"],
            "key_insight": "k",
            "sections": [
                {"heading": "H", "blocks": [{"type": "list", "items": ["a", "b"], "ordered": True}]}
            ],
        }
    )
    blk = r.sections[0].blocks[0]
    assert blk.type == "list" and blk.items == ["a", "b"] and blk.ordered is True
    assert r.references == []  # optional, defaults empty


def test_core_contributions_bounds_enforced() -> None:
    base = dict(title="T", key_insight="k",
                sections=[Section(heading="H", blocks=[ProseBlock(content="x")])])
    with pytest.raises(ValidationError):
        PaperReport(core_contributions=[], **base)
    with pytest.raises(ValidationError):
        PaperReport(core_contributions=["1", "2", "3", "4", "5", "6"], **base)


def test_code_block_in_union() -> None:
    section = Section.model_validate(
        {"heading": "h", "blocks": [{"type": "code", "language": "python", "content": "x = 1"}]}
    )
    blk = section.blocks[0]
    assert blk.type == "code" and blk.language == "python" and blk.content == "x = 1"


def test_code_block_language_optional() -> None:
    section = Section.model_validate(
        {"heading": "h", "blocks": [{"type": "code", "content": "make lint"}]}
    )
    assert section.blocks[0].language is None


def test_figure_block_url_optional() -> None:
    fig = FigureBlock(label="Figure 1", explanation="")
    assert fig.url is None
    with_url = FigureBlock(label="Fig", explanation="", url="https://x.test/a.png")
    assert with_url.url == "https://x.test/a.png"


def test_draft_from_paper_report() -> None:
    report = _report()
    draft = draft_from_paper_report(report)
    assert draft.pack_type == "paper"
    assert draft.summary is None
    assert draft.extras["key_insight"] == report.key_insight
    assert draft.extras["core_contributions"] == list(report.core_contributions)
    assert draft.extras["references"] == [
        {"citation": "Vaswani et al. (2017)", "why_interesting": "The Transformer."}
    ]
    assert draft.sections == report.sections


def test_pack_draft_requires_a_section() -> None:
    from app.pipeline.schemas import PackDraft

    with pytest.raises(ValidationError):
        PackDraft(title="T", pack_type="article", sections=[])


def test_unknown_block_type_rejected() -> None:
    with pytest.raises(ValidationError):
        PaperReport.model_validate(
            {
                "title": "T", "core_contributions": ["c"], "key_insight": "k",
                "sections": [{"heading": "H", "blocks": [{"type": "diagram", "content": "x"}]}],
            }
        )
