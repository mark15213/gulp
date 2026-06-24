from app.pipeline.adapters.note import note_to_normdoc


def test_note_becomes_single_block_normdoc() -> None:
    doc = note_to_normdoc("My note", "Remember this idea.")
    assert doc.media_type == "note"
    assert doc.title == "My note"
    assert doc.content_body == "Remember this idea."
    assert len(doc.blocks) == 1
    b = doc.blocks[0]
    assert b.text == "Remember this idea."
    assert doc.content_body[b.anchor.start : b.anchor.end] == b.text
    assert b.section_label is None
