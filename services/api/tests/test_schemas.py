import pytest
from pydantic import ValidationError

from app.schemas.capture import CaptureRequest


def test_accepts_a_url_only_request():
    req = CaptureRequest(url="https://a.com/x")
    assert req.url == "https://a.com/x"
    assert req.tags == []


def test_accepts_a_text_only_request():
    assert CaptureRequest(text="a thought").text == "a thought"


def test_rejects_both_url_and_text():
    with pytest.raises(ValidationError):
        CaptureRequest(url="https://a.com", text="also a note")


def test_rejects_neither():
    with pytest.raises(ValidationError):
        CaptureRequest(note="annotation only")
