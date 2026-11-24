from datetime import datetime, timedelta, timezone


def _view(client, user, restaurant_id, **extra):
    body = {"restaurant_id": restaurant_id, **extra}
    response = client.post("/analytics/restaurant-view", json=body, headers=user["headers"])
    assert response.status_code == 200, response.text


def test_recent_views_grouped_and_ordered(client, make_user):
    user = make_user()
    other = make_user()
    earlier = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _view(client, user, "1", viewed_at=earlier)
    _view(client, user, "2")
    _view(client, user, "1")
    _view(client, other, "3")

    items = client.get("/me/recent-views", headers=user["headers"]).json()["items"]
    assert [(i["restaurant_id"], i["view_count"]) for i in items] == [("1", 2), ("2", 1)]


def test_viewed_at_outside_window_uses_server_time(client, make_user):
    user = make_user()
    _view(client, user, "1", viewed_at="2020-01-01T00:00:00Z")
    item = client.get("/me/recent-views", headers=user["headers"]).json()["items"][0]
    last = datetime.fromisoformat(item["last_viewed_at"].replace("Z", "+00:00"))
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    assert datetime.now(timezone.utc) - last < timedelta(minutes=5)


def test_remove_and_clear_hide_views_but_keep_analytics(client, make_user):
    user = make_user()
    client.put("/me/saved/1", headers=user["headers"])
    _view(client, user, "1")
    _view(client, user, "2")

    after_remove = client.delete("/me/recent-views/1", headers=user["headers"]).json()["items"]
    assert [i["restaurant_id"] for i in after_remove] == ["2"]

    after_clear = client.delete("/me/recent-views", headers=user["headers"]).json()["items"]
    assert after_clear == []
    assert client.get("/me/recent-views", headers=user["headers"]).json()["items"] == []

    summary = client.get("/analytics/saved-rarely-viewed").json()
    assert summary["places"][0]["avg_views_after_saving"] == 1.0


def test_recent_views_require_session(client):
    assert client.get("/me/recent-views").status_code == 401
