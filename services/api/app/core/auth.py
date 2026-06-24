"""Auth stub (spec C6): returns the seeded dev user. Swap for real sign-in (S0)."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from gulp_shared.models.user import DEV_USER_ID, User


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.get(User, DEV_USER_ID)
    if user is None:
        raise RuntimeError("dev user not seeded — run `just migrate-up`")
    return user
