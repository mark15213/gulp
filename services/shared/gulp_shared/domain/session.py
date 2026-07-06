"""Session composition primitives (S4 design §4.2, C7). Pure over lightweight
CardRefs so the ordering rules are table-testable without the DB."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

CARDS_PER_MINUTE = 3


@dataclass(frozen=True)
class CardRef:
    card_id: str
    source_id: str


def cap_for(target_minutes: int, cards_per_minute: int = CARDS_PER_MINUTE) -> int:
    return max(1, target_minutes * cards_per_minute)


def prioritize(
    due_at_risk: list[CardRef], due: list[CardRef],
    new: list[CardRef], retests: list[CardRef], cap: int,
) -> list[CardRef]:
    picked: list[CardRef] = []
    for bucket in (due_at_risk, due, new, retests):
        for ref in bucket:
            if len(picked) >= cap:
                return interleave(picked)
            picked.append(ref)
    return interleave(picked)


def interleave(items: list[CardRef]) -> list[CardRef]:
    """Round-robin by source (first-seen order) so no two consecutive share a
    source when more than one source is present."""
    buckets: dict[str, deque[CardRef]] = defaultdict(deque)
    order: list[str] = []
    for it in items:
        if it.source_id not in buckets:
            order.append(it.source_id)
        buckets[it.source_id].append(it)
    out: list[CardRef] = []
    while any(buckets[s] for s in order):
        for s in order:
            if buckets[s]:
                out.append(buckets[s].popleft())
    return out
