import json

from app.export.archive import find_entry, read_zip
from app.export.builder import build_job_archive
from app.export.templates import claude_md, pack_schema
from app.pipeline.normdoc import Anchor, NormBlock, NormDoc


def _doc() -> NormDoc:
    body = "Attention weighs tokens by relevance."
    return NormDoc(title="A", lang="en", media_type="article", content_body=body,
                   blocks=[NormBlock(text=body, anchor=Anchor(start=0, end=len(body)))])


def test_pack_schema_and_claude_md():
    schema = pack_schema()
    assert "properties" in schema and "sections" in schema["properties"] and "facets" in schema["properties"]
    cm = claude_md()
    for needle in ("result/pack.json", "input/norm_doc.json", "schema/pack.schema.json", "English"):
        assert needle in cm


def test_build_job_archive_has_all_entries():
    data = build_job_archive(snapshot_id="s1", owner_id="o1", normdoc=_doc(), created_at="2026-06-26T00:00:00Z")
    files = read_zip(data)
    for suffix in ("CLAUDE.md", "README.md", "manifest.json", "input/norm_doc.json",
                   "schema/pack.schema.json", "result/HOWTO.txt"):
        assert find_entry(files, suffix)  # present, non-empty
    nd = json.loads(find_entry(files, "input/norm_doc.json"))
    assert nd["title"] == "A" and nd["blocks"][0]["text"].startswith("Attention")
    man = json.loads(find_entry(files, "manifest.json"))
    assert man["snapshot_id"] == "s1" and man["job_kind"] == "digest"
