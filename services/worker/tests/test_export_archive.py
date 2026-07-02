import json

import pytest
from app.export.archive import find_entry, read_zip, write_zip
from app.export.manifest import FORMAT_VERSION, build_manifest, parse_manifest


def test_write_then_read_round_trips():
    data = write_zip({"a/b.txt": b"hello", "m.json": b"{}"})
    files = read_zip(data)
    assert files["a/b.txt"] == b"hello"
    assert find_entry(files, "b.txt") == b"hello"


def test_read_zip_rejects_zip_slip():
    evil = write_zip({"../escape.txt": b"x"})
    with pytest.raises(ValueError):
        read_zip(evil)


def test_read_zip_rejects_oversize():
    big = write_zip({"big.bin": b"x" * 1000})
    with pytest.raises(ValueError):
        read_zip(big, max_total=10)


def test_manifest_round_trip_and_validation():
    m = build_manifest(snapshot_id="s1", owner_id="o1", input_sha256="abc",
                       created_at="2026-06-26T00:00:00Z")
    assert m["format_version"] == FORMAT_VERSION and m["job_kind"] == "digest"
    parsed = parse_manifest(json.dumps(m).encode())
    assert parsed["snapshot_id"] == "s1"
    with pytest.raises(ValueError):
        parse_manifest(json.dumps({"job_kind": "nope"}).encode())
    with pytest.raises(ValueError):
        parse_manifest(json.dumps({**m, "format_version": 999}).encode())
