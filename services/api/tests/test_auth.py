from app.core.auth import get_current_user
from gulp_shared.models.user import DEV_USER_ID


def test_get_current_user_returns_the_seeded_dev_user(db):
    user = get_current_user(db=db)
    assert user.id == DEV_USER_ID
