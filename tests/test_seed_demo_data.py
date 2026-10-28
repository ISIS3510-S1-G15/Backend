import pytest
from sqlalchemy import func

from app import models
from scripts.seed_demo_data import DEMO_PASSWORD, main

ADMIN = "demo01@uniandes.edu.co"


@pytest.fixture
def seeded(client, monkeypatch):
    assert main([]) == 0
    monkeypatch.setenv("ANALYTICS_ADMIN_EMAILS", ADMIN)
    response = client.post("/auth/login", json={"email": ADMIN, "password": DEMO_PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_second_run_is_blocked(seeded, capsys, db):
    before = db.query(func.count(models.AppOpen.id)).scalar()
    assert main([]) == 1
    assert "Ya existen usuarios de demostracion" in capsys.readouterr().err
    assert db.query(func.count(models.AppOpen.id)).scalar() == before


def test_dry_run_writes_nothing(db):
    assert main(["--dry-run"]) == 0
    assert db.query(func.count(models.User.id)).scalar() == 0


def test_weekly_app_opens(client, seeded):
    summary = client.get("/analytics/app-opens/weekly").json()
    assert summary["active_users"] == 12
    assert summary["user_weeks"] >= 40
    assert 2 <= summary["average_opens_per_user_per_week"] <= 8
    assert all(slot["count"] > 0 for slot in summary["opens_by_meal_slot"])


def test_occupancy_check_rate(client, seeded):
    summary = client.get("/analytics/occupancy-check-rate").json()
    assert summary["checks"] > 50
    assert summary["go_decisions"] > 30
    assert 40 <= summary["check_before_go_rate"] <= 95
    assert summary["checks_without_data"] > 0
    assert len(summary["by_restaurant"]) == 4
    legacy = client.get("/analytics/occupancy-checks").json()
    assert len(legacy) == 4 and all(item["selection_rate"] > 0 for item in legacy)


def test_filter_usage_ranking(client, seeded):
    usage = client.get("/analytics/filter-usage").json()
    assert usage[0]["filter"] == "Vegan options"
    assert {item["screen"] for item in usage} == {"home", "search", "map"}


def test_onboarding_completion(client, seeded):
    summary = client.get("/analytics/onboarding-completion").json()
    assert summary["started"] == 40
    assert 45 <= summary["completion_rate"] <= 92
    steps = [item["sessions"] for item in summary["reached_by_step"]]
    assert steps == sorted(steps, reverse=True)


def test_profile_edits(client, seeded):
    by_field = {item["field"]: item for item in client.get("/analytics/profile-edits/by-field").json()}
    assert set(by_field) == {"dietary_restrictions", "cuisine_preferences"}
    assert len(client.get("/analytics/profile-edits").json()) == 8


def test_zero_result_searches(client, seeded):
    gaps = client.get("/analytics/search-gaps").json()
    assert gaps[0] == {"query": "mexican", "count": 14}
    assert len(gaps) == 10


def test_saved_rarely_viewed(client, seeded):
    summary = client.get("/analytics/saved-rarely-viewed").json()
    places = {place["restaurant_id"]: place for place in summary["places"]}
    assert set(places) == {"1", "2", "3", "4"}
    assert places["3"]["rarely_viewed_pct"] == 100.0
    assert places["4"]["rarely_viewed_pct"] == 100.0
    assert places["1"]["rarely_viewed_pct"] < places["3"]["rarely_viewed_pct"]
    assert places["1"]["avg_views_after_saving"] > places["3"]["avg_views_after_saving"]
    assert 0 < summary["rarely_viewed_pct"] < 100


def test_least_used_sections(client, seeded):
    report = client.get("/analytics/sections/least-used", headers=seeded).json()
    assert report["sufficient_data"] is True
    assert report["least_interaction_rate"] == "filters"
    classes = {item["section"]: item["classification"] for item in report["sections"]}
    assert classes == {
        "map": "healthy",
        "filters": "low_engagement",
        "details": "healthy",
        "favorites": "niche_high_engagement",
    }
    usage = client.get("/analytics/sections/usage", headers=seeded).json()
    assert usage["total_visits"] == 340
    assert all(section["sufficient_data"] for section in usage["sections"])
