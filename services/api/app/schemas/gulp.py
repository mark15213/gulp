"""Gulp session contract (S4 design §6) → OpenAPI → @gulp/api-client."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SessionCardOut(BaseModel):
    id: uuid.UUID
    card_type: Literal["flashcard", "mcq", "cloze"]
    prompt: str
    options: list[str] | None = None
    answer: str | None = None
    explanation: str | None = None
    source_title: str | None = None
    reason: Literal["new", "due", "retest", "at_risk"]
    daily: Literal["new", "learning", "known"]


class SessionOut(BaseModel):
    id: uuid.UUID
    scope_type: str
    target_minutes: int
    status: str
    started_at: datetime | None
    cards: list[SessionCardOut]


class ReviewIn(BaseModel):
    card_id: uuid.UUID
    grade: Literal["got_it", "fuzzy", "missed"]
    response: str | None = None


class CardMasteryOut(BaseModel):
    ladder: str
    daily: str
    next_review_at: datetime | None
    interval_days: float


class ReviewOut(BaseModel):
    mastery: CardMasteryOut
    next_card: SessionCardOut | None
    done: bool


class SnoozeIn(BaseModel):
    card_id: uuid.UUID


class SessionStartIn(BaseModel):
    scope_type: Literal["daily", "at_risk", "free_explore"] = "daily"
    target_minutes: int | None = None


class NextUp(BaseModel):
    due_count: int
    inbox_count: int


class SummaryOut(BaseModel):
    reviewed_count: int
    newly_mastered: int
    still_fuzzy: int
    streak_days: int
    next_up: NextUp
