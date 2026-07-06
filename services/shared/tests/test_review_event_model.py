import uuid
from gulp_shared.models import ReviewEvent, ReviewGrade


def test_review_grade_values():
    assert [g.value for g in ReviewGrade] == ["got_it", "fuzzy", "missed"]


def test_review_event_construct():
    e = ReviewEvent(
        owner_id=uuid.uuid4(), session_id=uuid.uuid4(), card_id=uuid.uuid4(),
        grade=ReviewGrade.got_it,
    )
    assert e.response is None
    assert e.grade is ReviewGrade.got_it
