import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models, section_catalog

EVENTS_URL = "/analytics/sections/events"
USAGE_URL = "/analytics/sections/usage"
LEAST_USED_URL = "/analytics/sections/least-used"


def view(section, visit_id=None, at=None, event_id=None):
    return {
        "event_id": str(event_id or uuid.uuid4()),
        "event_type": "section_view",
        "section": section,
        "visit_id": str(visit_id or uuid.uuid4()),
        "client_timestamp": (at or datetime.now(timezone.utc)).isoformat(),
    }


def interaction(section, action, visit_id, at=None, event_id=None):
    return {
        "event_id": str(event_id or uuid.uuid4()),
        "event_type": "section_interaction",
        "section": section,
        "action": action,
        "visit_id": str(visit_id),
        "client_timestamp": (at or datetime.now(timezone.utc)).isoformat(),
    }


@pytest.fixture
def admin(make_user, monkeypatch):
    user = make_user("Admin")
    monkeypatch.setenv("ANALYTICS_ADMIN_EMAILS", user["email"])
    return user


def post(client, user, *events):
    return client.post(EVENTS_URL, json={"events": list(events)}, headers=user["headers"])


def section_row(client, admin, name, **params):
    body = client.get(USAGE_URL, params=params, headers=admin["headers"]).json()
    return next(row for row in body["sections"] if row["section"] == name)


def test_valid_event_is_stored(client, make_user, db):
    user = make_user()
    event = view("map")
    response = post(client, user, event)
    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "duplicates": 0}
    stored = db.get(models.SectionEvent, uuid.UUID(event["event_id"]))
    assert stored.user_id == user["id"]
    assert stored.section == "map"
    assert stored.event_type == "section_view"
    assert stored.received_at is not None


def test_invalid_section_is_rejected(client, make_user):
    event = view("map")
    event["section"] = "profile"
    assert post(client, make_user(), event).status_code == 422


def test_invalid_event_type_is_rejected(client, make_user):
    event = view("map")
    event["event_type"] = "section_click"
    assert post(client, make_user(), event).status_code == 422


def test_action_must_belong_to_section(client, make_user):
    event = interaction("map", "favorite_added", uuid.uuid4())
    assert post(client, make_user(), event).status_code == 422


def test_view_with_action_is_rejected(client, make_user):
    event = view("map")
    event["action"] = "marker_selected"
    assert post(client, make_user(), event).status_code == 422


def test_future_and_old_timestamps_are_rejected(client, make_user):
    user = make_user()
    future = view("map", at=datetime.now(timezone.utc) + timedelta(hours=1))
    old = view("map", at=datetime.now(timezone.utc) - timedelta(days=30))
    assert post(client, user, future).status_code == 422
    assert post(client, user, old).status_code == 422


def test_oversized_extra_is_rejected(client, make_user):
    event = view("map")
    event["extra"] = {f"k{i}": "v" for i in range(6)}
    assert post(client, make_user(), event).status_code == 422


def test_duplicate_event_counts_once(client, make_user, admin):
    user = make_user()
    event = view("map")
    assert post(client, user, event).json() == {"accepted": 1, "duplicates": 0}
    assert post(client, user, event).json() == {"accepted": 0, "duplicates": 1}
    assert section_row(client, admin, "map")["visits"] == 1


def test_user_id_comes_from_token_not_body(client, make_user, db):
    first = make_user()
    second = make_user()
    event = view("map")
    event["user_id"] = second["id"]
    post(client, first, event)
    assert db.get(models.SectionEvent, uuid.UUID(event["event_id"])).user_id == first["id"]


def test_events_require_authentication(client):
    assert client.post(EVENTS_URL, json={"events": [view("map")]}).status_code == 401


def test_metrics_with_known_data(client, make_user, admin):
    alice = make_user()
    bob = make_user()
    v1, v2, v3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    post(
        client,
        alice,
        view("map", v1),
        interaction("map", "marker_selected", v1),
        interaction("map", "restaurant_selected", v1),
        view("map", v2),
    )
    post(client, bob, view("map", v3), view("filters"), view("details"), view("favorites"))
    map_row = section_row(client, admin, "map")
    assert map_row["visits"] == 3
    assert map_row["interactions"] == 2
    assert map_row["unique_users"] == 2
    assert map_row["interactions_per_visit"] == round(2 / 3, 4)
    assert map_row["visits_with_interaction"] == 1
    assert map_row["interaction_rate"] == round(1 / 3, 4)
    assert map_row["share_of_visits"] == round(3 / 6, 4)
    assert map_row["share_of_interactions"] == 1.0
    assert map_row["sufficient_data"] is False


def test_interaction_only_counts_for_rate_when_visit_matches(client, make_user, admin):
    user = make_user()
    visit = uuid.uuid4()
    post(client, user, view("details", visit), interaction("favorites", "favorite_added", visit))
    assert section_row(client, admin, "details")["interaction_rate"] == 0.0
    favorites = section_row(client, admin, "favorites")
    assert favorites["interactions"] == 1
    assert favorites["visits_with_interaction"] == 0
    assert favorites["interaction_rate"] is None


def test_sections_without_activity_do_not_divide_by_zero(client, admin):
    body = client.get(USAGE_URL, headers=admin["headers"]).json()
    assert body["total_visits"] == 0
    for row in body["sections"]:
        assert row["visits"] == 0
        assert row["interactions_per_visit"] is None
        assert row["interaction_rate"] is None
        assert row["share_of_visits"] is None
        assert row["share_of_interactions"] is None
        assert row["classification"] == "insufficient_data"


def test_date_window_filters_events(client, make_user, admin):
    user = make_user()
    now = datetime.now(timezone.utc)
    post(
        client,
        user,
        view("map", at=now - timedelta(days=3)),
        view("map", at=now - timedelta(hours=1)),
    )
    start = (now - timedelta(days=1)).isoformat()
    assert section_row(client, admin, "map", start=start)["visits"] == 1
    assert section_row(client, admin, "map")["visits"] == 2
    end = (now - timedelta(days=2)).isoformat()
    assert section_row(client, admin, "map", end=end)["visits"] == 1


def test_least_used_ranks_and_classifies(client, make_user, admin, monkeypatch):
    monkeypatch.setattr(section_catalog, "MIN_VISITS_PER_SECTION", 2)
    user = make_user()
    events = []
    for _ in range(10):
        visit = uuid.uuid4()
        events += [view("map", visit), interaction("map", "marker_selected", visit)]
    for _ in range(10):
        visit = uuid.uuid4()
        events += [view("details", visit), interaction("details", "reviews_opened", visit)]
    for _ in range(10):
        events.append(view("filters"))
    for _ in range(2):
        visit = uuid.uuid4()
        events += [view("favorites", visit), interaction("favorites", "saved_item_selected", visit)]
    for start in range(0, len(events), 50):
        post(client, user, *events[start : start + 50])
    body = client.get(LEAST_USED_URL, headers=admin["headers"]).json()
    assert body["sufficient_data"] is True
    assert body["least_visited"] == "favorites"
    assert body["least_interaction_rate"] == "filters"
    assert body["ranking_by_visits"][0]["section"] == "favorites"
    by_section = {row["section"]: row for row in body["sections"]}
    assert by_section["filters"]["classification"] == "low_engagement"
    assert by_section["favorites"]["classification"] == "niche_high_engagement"
    assert by_section["map"]["classification"] == "healthy"


def test_insufficient_data_is_reported(client, make_user, admin):
    post(client, make_user(), view("map"))
    body = client.get(LEAST_USED_URL, headers=admin["headers"]).json()
    assert body["sufficient_data"] is False
    assert body["least_visited"] is None
    assert [row["section"] for row in body["ranking_by_interaction_rate"]] == ["map"]


def test_aggregate_endpoints_are_restricted(client, make_user):
    regular = make_user()
    for url in (USAGE_URL, LEAST_USED_URL):
        assert client.get(url).status_code == 401
        assert client.get(url, headers=regular["headers"]).status_code == 403


def test_existing_data_untouched_and_old_endpoints_work(client, make_user):
    user = make_user()
    client.post("/analytics/app-open", json={"meal_slot": "Lunch"}, headers=user["headers"])
    post(client, user, view("map"))
    assert client.get("/").status_code == 200
    assert client.get("/analytics/filter-usage").status_code == 200
    assert client.get("/auth/me", headers=user["headers"]).status_code == 200
