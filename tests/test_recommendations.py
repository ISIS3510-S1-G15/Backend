from datetime import timedelta

from app import models
from app.routers.recommendations import occupancy_level


def _show(client, user, recommended, level, alternative=None):
    body = {"recommended_id": recommended, "recommended_level": level, "alternative_id": alternative}
    response = client.post("/analytics/recommendation-shown", json=body, headers=user["headers"])
    assert response.status_code == 200, response.text


def _go(client, user, restaurant):
    body = {"restaurant_id": restaurant, "event": "go_decision"}
    assert client.post("/analytics/occupancy-event", json=body, headers=user["headers"]).status_code == 200


def _level(summary, name):
    return next(row for row in summary["by_level"] if row["occupancy_level"] == name)


def test_occupancy_level_uses_app_thresholds():
    assert occupancy_level(None) == "no_data"
    assert occupancy_level(0.5) == "not_crowded"
    assert occupancy_level(1.0) == "moderate"
    assert occupancy_level(2.0) == "busy"


def test_recommendation_shown_requires_login(client):
    response = client.post("/analytics/recommendation-shown", json={"recommended_id": "r1"})
    assert response.status_code == 401


def test_alternative_rate_by_occupancy_level(client, make_user):
    calm, busy_kept, busy_switched, other = make_user(), make_user(), make_user(), make_user()

    _show(client, calm, "r1", 0.2)
    _go(client, calm, "r1")

    _show(client, busy_kept, "r2", 2.0, "r3")
    _go(client, busy_kept, "r2")

    _show(client, busy_switched, "r2", 1.8, "r3")
    _go(client, busy_switched, "r3")

    _show(client, other, "r4", None)
    _go(client, other, "r9")

    summary = client.get("/analytics/occupancy-alternatives").json()
    assert summary["recommendations"] == 4
    assert summary["decisions"] == 4
    assert summary["alternative_rate"] == 50.0

    busy = _level(summary, "busy")
    assert busy["decisions"] == 2
    assert busy["chose_recommended"] == 1
    assert busy["chose_suggested_alternative"] == 1
    assert busy["alternative_rate"] == 50.0
    assert _level(summary, "not_crowded")["alternative_rate"] == 0.0
    assert _level(summary, "no_data")["chose_other_place"] == 1

    export = client.get("/analytics/occupancy-alternatives/export").text
    assert "r2,busy,r3,r3,suggested_alternative" in export


def test_decisions_outside_window_are_ignored(client, make_user, db):
    user = make_user()
    _show(client, user, "r1", 1.9, "r2")
    event = db.query(models.RecommendationEvent).one()
    event.timestamp -= timedelta(hours=2)
    db.commit()
    _go(client, user, "r2")

    summary = client.get("/analytics/occupancy-alternatives").json()
    assert summary["recommendations"] == 1
    assert summary["decisions"] == 0
