import json

import pytest
from pydantic import ValidationError

from app.export.archive import write_zip
from app.export.importer import import_result_archive

_VALID = {
    "summary": "s", "background": None, "confidence": 0.8,
    "sections": [{"heading": "H", "blocks": [{"type": "prose", "content": "c"}]}],
    "facets": [{"element_type": "claim", "text": "x"}],
}


def test_import_valid_result():
    data = write_zip({"gulp-job-x/result/pack.json": json.dumps(_VALID).encode()})
    out = import_result_archive(data)
    assert out.summary == "s" and out.sections[0].blocks[0].content == "c"


def test_import_missing_pack_raises():
    data = write_zip({"gulp-job-x/manifest.json": b"{}"})
    with pytest.raises(ValueError):
        import_result_archive(data)


def test_import_invalid_shape_raises():
    data = write_zip({"result/pack.json": json.dumps({"summary": "s"}).encode()})  # missing sections/facets
    with pytest.raises(ValidationError):
        import_result_archive(data)
