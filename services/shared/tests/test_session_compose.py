from gulp_shared.domain.session import CardRef, cap_for, interleave, prioritize


def r(cid, sid):
    return CardRef(card_id=cid, source_id=sid)


def test_cap_from_minutes():
    assert cap_for(5) == 15
    assert cap_for(1) == 3
    assert cap_for(0) == 1  # never zero


def test_prioritize_respects_order_and_cap():
    due_ar = [r("a", "s1")]
    due = [r("b", "s2"), r("c", "s1")]
    new = [r("d", "s3")]
    retests = [r("e", "s2")]
    out = prioritize(due_ar, due, new, retests, cap=3)
    ids = {c.card_id for c in out}
    assert len(out) == 3
    assert "a" in ids  # highest priority always in
    assert "e" not in ids  # retests are last, cut by the cap


def test_interleave_avoids_consecutive_same_source():
    items = [r("a", "s1"), r("b", "s1"), r("c", "s2")]
    out = interleave(items)
    sources = [c.source_id for c in out]
    assert not any(sources[i] == sources[i + 1] for i in range(len(sources) - 1))
    assert {c.card_id for c in out} == {"a", "b", "c"}
