from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def test_normdoc_round_trips_and_anchors_slice_content_body() -> None:
    body = "First paragraph.\n\nSecond paragraph."
    blocks = [
        NormBlock(text="First paragraph.", section_label="Intro", anchor=Anchor(start=0, end=16)),
        NormBlock(text="Second paragraph.", anchor=Anchor(start=18, end=35)),
    ]
    doc = NormDoc(title="T", lang="en", media_type="note", content_body=body, blocks=blocks)

    # anchors slice content_body exactly
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text

    # JSON round-trip (forward-compat for the export job spec)
    again = NormDoc.model_validate_json(doc.model_dump_json())
    assert again == doc
    assert again.blocks[0].anchor.kind == "char_range"
