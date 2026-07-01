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


def test_normdoc_sanitizes_lone_surrogates_and_stays_json_serializable() -> None:
    # pypdf text extraction / html.unescape can emit lone UTF-16 surrogate code
    # points (e.g. an astral char split into its two halves) that can't be UTF-8
    # encoded, which crashed the export builder's model_dump_json(). chr(0xD83D)
    # / chr(0xDE09) construct those lone surrogates unambiguously.
    hi, lo = chr(0xD83D), chr(0xDE09)
    dirty = f"hi {hi}{lo} there"
    doc = NormDoc(
        title=f"t{hi}",
        media_type="pdf",
        content_body=dirty,
        blocks=[NormBlock(text=dirty, anchor=Anchor(start=0, end=len(dirty)))],
    )

    # Serialization must not raise (this is what crashed build_export), and the
    # result must be UTF-8 encodable.
    doc.model_dump_json().encode("utf-8")

    # Surrogates replaced by U+FFFD, length-preserving so anchors still slice.
    assert hi not in doc.content_body and lo not in doc.content_body
    assert "�" in doc.content_body
    assert hi not in doc.title
    for b in doc.blocks:
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text


def test_normdoc_strips_nul_bytes() -> None:
    # pypdf also emits NUL (0x00) bytes from broken PDF encodings. UTF-8/JSON
    # accept them, but PostgreSQL text fields reject them, so content_body must
    # be cleaned length-preservingly (anchors stay valid).
    dirty = f"before{chr(0)}after"
    doc = NormDoc(
        title=f"t{chr(0)}",
        media_type="pdf",
        content_body=dirty,
        blocks=[NormBlock(text=dirty, anchor=Anchor(start=0, end=len(dirty)))],
    )

    assert "\x00" not in doc.content_body
    assert "\x00" not in doc.title
    for b in doc.blocks:
        assert "\x00" not in b.text
        assert doc.content_body[b.anchor.start : b.anchor.end] == b.text
