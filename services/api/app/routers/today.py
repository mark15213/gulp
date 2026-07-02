"""Today endpoint — thin (docs/05 D4)."""

from fastapi import APIRouter, Depends
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.today import TodayOut
from app.services.today import today_summary

router = APIRouter()


@router.get("/today", response_model=TodayOut)
def get_today(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TodayOut:
    return today_summary(db, user.id)
