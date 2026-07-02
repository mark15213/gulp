import json

import pytest
from app.export.archive import write_zip
from app.export.importer import import_result_archive
from pydantic import ValidationError

_VALID = {
    "title": "T",
    "core_contributions": ["c"],
    "key_insight": "k",
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "references": [],
}


def test_import_valid_result():
    data = write_zip({"gulp-job-x/result/pack.json": json.dumps(_VALID).encode()})
    out = import_result_archive(data)
    assert out.title == "T" and out.sections[0].blocks[0].content == "c"


def test_import_missing_pack_raises():
    data = write_zip({"gulp-job-x/manifest.json": b"{}"})
    with pytest.raises(ValueError):
        import_result_archive(data)


def test_import_invalid_shape_raises():
    # missing required core_contributions / key_insight / sections
    data = write_zip({"result/pack.json": json.dumps({"title": "T"}).encode()})
    with pytest.raises(ValidationError):
        import_result_archive(data)
