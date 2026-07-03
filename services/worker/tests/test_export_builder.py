import json

from app.export.archive import find_entry, read_zip
from app.export.builder import build_cards_job_archive, build_job_archive
from app.export.templates import cards_schema, claude_md, pack_schema, prompt_md
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(title="A", lang="en", media_type="article", content_body=body,
                   blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))])


def test_pack_schema_prompt_and_claude_md():
    schema = pack_schema()
    props = schema["properties"]
    assert "sections" in props and "core_contributions" in props and "key_insight" in props
    assert "facets" not in props and "summary" not in props
    cm = claude_md()
    for needle in ("result/pack.json", "input/norm_doc.json",
                   "schema/pack.schema.json", "prompt.md"):
        assert needle in cm
    pm = prompt_md()
    assert "expert" in pm.lower() and "core_contributions" in pm and "key_insight" in pm
    cs = cards_schema()
    assert "cards" in cs["properties"]  # the shared CardsPayload contract


def test_build_job_archive_has_all_entries():
    data = build_job_archive(snapshot_id="s1", owner_id="o1", normdoc=_doc(),
                             created_at="2026-06-26T00:00:00Z")
    files = read_zip(data)
    for suffix in ("CLAUDE.md", "prompt.md", "manifest.json", "input/norm_doc.json",
                   "schema/pack.schema.json", "schema/cards.schema.json",
                   "result/HOWTO.txt"):
        assert find_entry(files, suffix)  # present, non-empty
    assert not any(name.endswith("README.md") for name in files)  # README dropped
    nd = json.loads(find_entry(files, "input/norm_doc.json"))
    assert nd["title"] == "A" and nd["blocks"][0]["text"].startswith("Attention")
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["snapshot_id"] == "s1" and man["job_kind"] == "digest"


def test_build_cards_job_archive_has_all_entries():
    data = build_cards_job_archive(
        snapshot_id="s1",
        owner_id="o1",
        pack_text="# BERT\nMasked language modeling.",
        conversation_text="user: why mask?\nassistant: bidirectional context.",
        created_at="2026-07-03T00:00:00Z",
    )
    files = read_zip(data)
    for suffix in ("CLAUDE.md", "prompt.md", "manifest.json", "input/pack.md",
                   "input/conversation.md", "schema/cards.schema.json", "result/HOWTO.txt"):
        assert find_entry(files, suffix)
    assert not any(name.endswith("pack.schema.json") for name in files)  # cards job, not digest
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["snapshot_id"] == "s1" and man["job_kind"] == "cards"
    assert b"BERT" in find_entry(files, "input/pack.md")
    assert "cards" in json.loads(find_entry(files, "schema/cards.schema.json"))["properties"]


def test_build_cards_job_archive_omits_empty_conversation():
    data = build_cards_job_archive(
        snapshot_id="s1", owner_id="o1", pack_text="pack", conversation_text="",
        created_at="2026-07-03T00:00:00Z",
    )
    files = read_zip(data)
    assert not any(name.endswith("conversation.md") for name in files)
