from sqlalchemy import inspect

from app.database import engine


def _select(client, user, ms, restaurant="r1", slot="Lunch"):
    body = {"restaurant_id": restaurant, "ms_since_app_open": ms}
    if slot is not None:
        body["meal_slot"] = slot
    return client.post("/analytics/place-selection", json=body, headers=user["headers"])


def test_requires_login(client):
    response = client.post("/analytics/place-selection", json={"restaurant_id": "r1", "ms_since_app_open": 1000})
    assert response.status_code == 401


def test_rejects_invalid_payloads(client, make_user):
    user = make_user()
    assert _select(client, user, -1).status_code == 422
    assert _select(client, user, 24 * 60 * 60 * 1000 + 1).status_code == 422
    assert _select(client, user, 1000, restaurant="").status_code == 422
    assert _select(client, user, 1000, slot="Brunch").status_code == 422


def test_summary_and_export(client, make_user):
    first, second = make_user(), make_user()
    assert _select(client, first, 30_000).json() == {"saved": True}
    assert _select(client, first, 90_000, slot="Dinner").status_code == 200
    assert _select(client, second, 600_000, restaurant="r2", slot=None).status_code == 200

    summary = client.get("/analytics/time-to-selection").json()
    overall = summary["overall"]
    assert overall["selections"] == 3
    assert overall["users"] == 2
    assert overall["avg_seconds"] == 240.0
    assert overall["median_seconds"] == 90.0
    assert overall["within_1min_pct"] == 33.3
    assert overall["within_5min_pct"] == 66.7
    slots = {row["meal_slot"]: row for row in summary["by_meal_slot"]}
    assert slots["Lunch"]["avg_seconds"] == 30.0
    assert slots[None]["selections"] == 1

    export = client.get("/analytics/time-to-selection/export")
    assert export.status_code == 200
    lines = export.text.strip().splitlines()
    assert lines[0] == "user_id,restaurant_id,meal_slot,seconds_since_app_open,received_at_utc"
    assert len(lines) == 4
    assert f"{first['id']},r1,Lunch,30.0," in export.text


def test_empty_summary(client):
    overall = client.get("/analytics/time-to-selection").json()["overall"]
    assert overall == {
        "selections": 0, "users": 0, "avg_seconds": None, "median_seconds": None,
        "p90_seconds": None, "within_1min_pct": None, "within_5min_pct": None,
    }


def test_does_not_touch_occupancy_events(client, make_user):
    user = make_user()
    _select(client, user, 5_000)
    assert client.get("/analytics/occupancy-check-rate").json()["go_decisions"] == 0
    assert "place_selection_events" in inspect(engine).get_table_names()


def test_my_time_to_selection(client, make_user):
    me, other = make_user(), make_user()
    empty = client.get("/analytics/time-to-selection/me", headers=me["headers"]).json()
    assert empty == {"campus_avg_seconds": None, "campus_selections": 0, "my_avg_seconds": None, "my_selections": 0}

    _select(client, me, 60_000)
    _select(client, me, 120_000)
    _select(client, other, 300_000)
    body = client.get("/analytics/time-to-selection/me", headers=me["headers"]).json()
    assert body == {"campus_avg_seconds": 160.0, "campus_selections": 3, "my_avg_seconds": 90.0, "my_selections": 2}
    assert client.get("/analytics/time-to-selection/me").status_code == 401
