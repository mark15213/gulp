import pytest
from app.pipeline.schemas import (
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
    TableBlock,
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


def test_unknown_block_type_rejected() -> None:
    with pytest.raises(ValidationError):
        PaperReport.model_validate(
            {
                "title": "T", "core_contributions": ["c"], "key_insight": "k",
                "sections": [{"heading": "H", "blocks": [{"type": "diagram", "content": "x"}]}],
            }
        )
