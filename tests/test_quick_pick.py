from app import models

QUICK_PICK = "/analytics/time-to-selection/me/quick-pick"
BY_SOURCE = "/analytics/time-to-selection/by-source"


def _select(client, user, seconds, restaurant="3", slot="Lunch", source=None):
    body = {"restaurant_id": restaurant, "ms_since_app_open": int(seconds * 1000), "meal_slot": slot}
    if source is not None:
        body["source"] = source
    response = client.post("/analytics/place-selection", json=body, headers=user["headers"])
    assert response.status_code == 200, response.text
    return response


def _quick_pick(client, user, slot="Lunch"):
    response = client.get(QUICK_PICK, params={"meal_slot": slot}, headers=user["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _sources(client):
    body = client.get(BY_SOURCE).json()
    return {row["source"]: row for row in body["by_source"]}, body["quick_pick_share_pct"]


def test_source_defaults_to_detail_and_validates(client, make_user):
    user = make_user()
    _select(client, user, 30)
    _select(client, user, 10, source="quick_pick")
    body = {"restaurant_id": "3", "ms_since_app_open": 1000, "source": "home"}
    assert client.post("/analytics/place-selection", json=body, headers=user["headers"]).status_code == 422

    rows, _ = _sources(client)
    assert rows["detail"]["selections"] == 1
    assert rows["quick_pick"]["selections"] == 1


def test_quick_pick_requires_login_and_valid_slot(client, make_user):
    assert client.get(QUICK_PICK, params={"meal_slot": "Lunch"}).status_code == 401
    user = make_user()
    assert client.get(QUICK_PICK, params={"meal_slot": "Brunch"}, headers=user["headers"]).status_code == 422
    assert client.get(QUICK_PICK, headers=user["headers"]).status_code == 422


def test_no_data_shows_nothing(client, make_user):
    assert _quick_pick(client, make_user()) == {
        "meal_slot": "Lunch", "kind": None, "candidates": [], "times_chosen": 0,
        "my_avg_seconds": None, "campus_avg_seconds": None, "my_selections": 0,
    }


def test_your_usual_for_a_slow_decider(client, make_user):
    me, other = make_user(), make_user()
    _select(client, me, 200, "3")
    _select(client, me, 180, "1")
    _select(client, me, 160, "3")
    _select(client, other, 60, "1")

    assert _quick_pick(client, me) == {
        "meal_slot": "Lunch", "kind": "your_usual", "candidates": ["3", "1"], "times_chosen": 2,
        "my_avg_seconds": 180.0, "campus_avg_seconds": 150.0, "my_selections": 3,
    }


def test_fast_decider_gets_no_card(client, make_user):
    me, other = make_user(), make_user()
    _select(client, me, 30, "3")
    _select(client, me, 40, "1")
    _select(client, me, 20, "3")
    _select(client, other, 300, "1")

    body = _quick_pick(client, me)
    assert body["kind"] is None
    assert body["candidates"] == []
    assert body["my_avg_seconds"] == 30.0
    assert body["campus_avg_seconds"] == 97.5


def test_averages_ignore_quick_pick_but_habit_counts_it(client, make_user):
    me, other = make_user(), make_user()
    _select(client, me, 200, "3")
    _select(client, me, 5, "3", source="quick_pick")
    _select(client, me, 5, "3", source="quick_pick")
    _select(client, other, 60, "1")

    body = _quick_pick(client, me)
    assert body["kind"] == "your_usual"
    assert body["candidates"] == ["3"]
    assert body["times_chosen"] == 3
    assert body["my_avg_seconds"] == 200.0
    assert body["my_selections"] == 1
    assert body["campus_avg_seconds"] == 130.0


def test_campus_favorite_for_a_new_user(client, make_user):
    me, first, second = make_user(), make_user(), make_user()
    _select(client, first, 90, "2", slot="Dinner")
    _select(client, first, 70, "2", slot="Dinner")
    _select(client, second, 50, "2", slot="Dinner")
    _select(client, second, 40, "4", slot="Dinner")

    body = _quick_pick(client, me, slot="Dinner")
    assert body["kind"] == "campus_favorite"
    assert body["candidates"] == ["2", "4"]
    assert body["times_chosen"] == 3
    assert body["my_selections"] == 0
    assert body["my_avg_seconds"] is None
    assert body["campus_avg_seconds"] == 62.5


def test_campus_favorite_needs_enough_picks(client, make_user):
    me, other = make_user(), make_user()
    _select(client, other, 90, "2", slot="Dinner")
    _select(client, other, 70, "2", slot="Dinner")
    assert _quick_pick(client, me, slot="Dinner")["kind"] is None


def test_tie_goes_to_the_most_recent_choice(client, make_user):
    me = make_user()
    _select(client, me, 100, "1")
    _select(client, me, 100, "1")
    _select(client, me, 100, "3")
    _select(client, me, 100, "3")

    body = _quick_pick(client, me)
    assert body["kind"] == "your_usual"
    assert body["candidates"] == ["3", "1"]


def test_meal_slots_do_not_mix(client, make_user):
    me, other = make_user(), make_user()
    _select(client, me, 200, "3")
    _select(client, me, 200, "3")
    _select(client, other, 100, "3")
    _select(client, other, 100, "3")

    assert _quick_pick(client, me, slot="Lunch")["kind"] == "your_usual"
    assert _quick_pick(client, me, slot="Breakfast") == {
        "meal_slot": "Breakfast", "kind": None, "candidates": [], "times_chosen": 0,
        "my_avg_seconds": None, "campus_avg_seconds": None, "my_selections": 0,
    }


def test_by_source_empty(client):
    rows, share = _sources(client)
    assert share is None
    empty = {
        "selections": 0, "users": 0, "avg_seconds": None, "median_seconds": None,
        "p90_seconds": None, "within_1min_pct": None, "within_5min_pct": None,
    }
    assert rows == {"detail": {"source": "detail", **empty}, "quick_pick": {"source": "quick_pick", **empty}}


def test_by_source_with_data_counts_legacy_rows_as_detail(client, make_user, db):
    me, other = make_user(), make_user()
    _select(client, me, 60)
    _select(client, other, 120)
    _select(client, me, 10, source="quick_pick")
    # A Sprint 3 row, written before the column existed.
    db.add(models.PlaceSelectionEvent(user_id=me["id"], restaurant_id="1", ms_since_app_open=30_000))
    db.commit()

    rows, share = _sources(client)
    assert rows["detail"]["selections"] == 3
    assert rows["detail"]["users"] == 2
    assert rows["detail"]["avg_seconds"] == 70.0
    assert rows["detail"]["median_seconds"] == 60.0
    assert rows["quick_pick"]["selections"] == 1
    assert rows["quick_pick"]["avg_seconds"] == 10.0
    assert rows["quick_pick"]["within_1min_pct"] == 100.0
    assert share == 25.0


def test_export_adds_source_column(client, make_user, db):
    me = make_user()
    db.add(models.PlaceSelectionEvent(user_id=me["id"], restaurant_id="1", ms_since_app_open=30_000))
    db.commit()
    _select(client, me, 10, "3", source="quick_pick")

    lines = client.get("/analytics/time-to-selection/export").text.strip().splitlines()
    assert lines[0].endswith(",source")
    assert lines[1].startswith(f"{me['id']},1,,30.0,") and lines[1].endswith(",detail")
    assert lines[2].startswith(f"{me['id']},3,Lunch,10.0,") and lines[2].endswith(",quick_pick")
