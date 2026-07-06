"""GET /today — gulp due/new counts + mastery tally (S4 §3.3)."""


def test_today_reports_due_and_tally(client, db, owner, make_accepted_card):  # type: ignore[no-untyped-def]
    make_accepted_card(db, owner)  # new card
    r = client.get("/today")
    body = r.json()
    assert "due_count" in body and "new_count" in body
    assert body["new_count"] >= 1
    assert set(body["mastery"]) == {"new", "learning", "known", "at_risk"}
