def test_start_review_complete_flow(client, db, owner, make_accepted_card):
    make_accepted_card(db, owner)
    r = client.post("/gulp/sessions", json={"scope_type": "daily"})
    assert r.status_code == 200
    sess = r.json()
    assert sess["status"] == "active" and len(sess["cards"]) >= 1
    card = sess["cards"][0]
    assert card["reason"] in ("new", "due", "retest", "at_risk")

    rev = client.post(f"/gulp/sessions/{sess['id']}/reviews",
                      json={"card_id": card["id"], "grade": "got_it"})
    assert rev.status_code == 200
    assert rev.json()["mastery"]["daily"] in ("new", "learning", "known")

    summ = client.post(f"/gulp/sessions/{sess['id']}/complete")
    assert summ.status_code == 200
    assert "streak_days" in summ.json()


def test_current_session_roundtrip(client, db, owner, make_accepted_card):
    make_accepted_card(db, owner)
    client.post("/gulp/sessions", json={"scope_type": "daily"})
    cur = client.get("/gulp/sessions/current")
    assert cur.status_code == 200 and cur.json() is not None


def test_scoped_scope_400(client):
    r = client.post("/gulp/sessions", json={"scope_type": "concept"})
    # Literal on SessionStartIn rejects concept at validation (422) — belt-and-
    # suspenders: the service also raises. Accept either 422 or 400.
    assert r.status_code in (400, 422)


def test_review_rejects_card_not_in_session(client, db, owner, make_accepted_card):
    # Ownership + membership guard (Task-9 review finding): reviewing a card
    # that is NOT part of the session's frozen composition is a 404.
    import uuid as _uuid
    make_accepted_card(db, owner)
    sess = client.post("/gulp/sessions", json={"scope_type": "daily"}).json()
    stranger = make_accepted_card(db, owner)  # a real card, but NOT in this session's plan
    assert str(stranger.id) not in [c["id"] for c in sess["cards"]]
    r = client.post(f"/gulp/sessions/{sess['id']}/reviews",
                    json={"card_id": str(stranger.id), "grade": "got_it"})
    assert r.status_code == 404
    # and a bogus session id is likewise 404
    r2 = client.post(f"/gulp/sessions/{_uuid.uuid4()}/reviews",
                     json={"card_id": sess["cards"][0]["id"], "grade": "got_it"})
    assert r2.status_code == 404
