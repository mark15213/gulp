"""SM-2-lite scheduler (S4 design §3.2, C3). Pure fold: (state, grade) -> state.
Constants are house-tuned SM-2 territory; the FSRS swap recomputes the same
columns from the same ReviewEvents (docs/01 §11)."""

from __future__ import annotations

from dataclasses import dataclass, replace

EASE_START = 2.3
EASE_FLOOR = 1.3
EASE_FUZZY_DROP = 0.05
EASE_MISS_DROP = 0.20


@dataclass(frozen=True)
class Scheduling:
    interval_days: float = 0.0
    ease: float = EASE_START
    reps: int = 0
    lapses: int = 0


def apply_review(s: Scheduling, grade: str, *, is_mcq: bool = False) -> Scheduling:
    if grade == "got_it":
        reps = s.reps + 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 3.0
        else:
            interval = float(round(s.interval_days * s.ease))
        return replace(s, reps=reps, interval_days=interval)
    if grade == "fuzzy":
        ease = max(EASE_FLOOR, round(s.ease - EASE_FUZZY_DROP, 4))
        interval = max(1.0, s.interval_days * 1.2)
        return replace(s, reps=s.reps + 1, ease=ease, interval_days=interval)
    if grade == "missed":
        ease = max(EASE_FLOOR, round(s.ease - EASE_MISS_DROP, 4))
        return replace(s, reps=0, lapses=s.lapses + 1, ease=ease, interval_days=1.0)
    raise ValueError(f"unknown grade {grade!r}")
