from app.pipeline.schemas import DigestBlock, DigestFacet, DigestResult, DigestSection


def test_digest_result_round_trips() -> None:
    r = DigestResult(
        summary="It explains attention.",
        background="Transformers context.",
        confidence=0.8,
        sections=[
            DigestSection(
                heading="Overview",
                blocks=[DigestBlock(content="Attention weighs tokens by relevance.")],
            )
        ],
        facets=[DigestFacet(element_type="key_term", text="attention")],
    )
    again = DigestResult.model_validate_json(r.model_dump_json())
    assert again == r
    assert again.sections[0].blocks[0].type == "prose"  # default


def test_block_type_and_facet_type_are_constrained() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DigestBlock(type="diagram", content="x")  # not in the Literal
    with pytest.raises(ValidationError):
        DigestFacet(element_type="opinion", text="x")  # not in the Literal
