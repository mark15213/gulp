"""Today aggregate — the "what should I do right now?" payload (docs/03 §7.9)."""

from pydantic import BaseModel

from app.schemas.capture import SnapshotOut


class TodayDigestItem(BaseModel):
    snapshot: SnapshotOut
    accepted_cards: int


class MasteryTally(BaseModel):
    new: int
    learning: int
    known: int
    at_risk: int


class TodayOut(BaseModel):
    accepted_cards: int
    card_sources: int
    ready_count: int
    digest: list[TodayDigestItem]
    inbox_count: int
    recent: list[SnapshotOut]
    due_count: int
    new_count: int
    mastery: MasteryTally
