from datetime import datetime

from sqlalchemy import func

from app import models

REVIEW = {"taste": 5, "attention": 4, "price": 3, "options": 4, "dietary_options": ["Vegan"], "comment": "Muy bueno"}


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_login_me(client):
    payload = {"name": "Ana", "email": "Ana@uniandes.edu.co", "password": "Password1!"}
    registered = client.post("/auth/register", json=payload)
    assert registered.status_code == 201
    assert registered.json()["user"]["email"] == "ana@uniandes.edu.co"

    logged = client.post("/auth/login", json={"email": "ana@uniandes.edu.co", "password": "Password1!"})
    assert logged.status_code == 200
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {logged.json()['access_token']}"})
    assert me.status_code == 200
    assert me.json()["name"] == "Ana"


def test_register_rejects_duplicates_and_foreign_domains(client):
    payload = {"name": "Ana", "email": "ana@uniandes.edu.co", "password": "Password1!"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409
    other = {**payload, "email": "ana@gmail.com"}
    assert client.post("/auth/register", json=other).status_code == 422


def test_wrong_password_is_unauthorized(client, make_user):
    user = make_user()
    response = client.post("/auth/login", json={"email": user["email"], "password": "Incorrecta1!"})
    assert response.status_code == 401


def test_password_is_stored_as_bcrypt_hash(client, make_user, db):
    make_user()
    stored = db.query(models.User).one().password_hash
    assert stored.startswith("$2b$") and "Password1!" not in stored


def test_protected_routes_require_token(client):
    for method, path in [("get", "/auth/me"), ("get", "/me/saved"), ("get", "/me/profile"), ("post", "/occupancy/reports")]:
        assert getattr(client, method)(path).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_saved_restaurants_flow(client, make_user):
    user = make_user()
    assert client.get("/me/saved", headers=user["headers"]).json() == {"restaurant_ids": []}
    client.put("/me/saved/r1", headers=user["headers"])
    client.put("/me/saved/r1", headers=user["headers"])
    after = client.put("/me/saved/r2", headers=user["headers"]).json()
    assert sorted(after["restaurant_ids"]) == ["r1", "r2"]
    assert client.delete("/me/saved/r1", headers=user["headers"]).json() == {"restaurant_ids": ["r2"]}


def test_profile_json_roundtrip(client, make_user):
    user = make_user()
    assert client.get("/me/profile", headers=user["headers"]).json()["completed"] is False
    body = {"name": "Ana", "cuisines": ["Mexican", "Italian"], "priorities": ["Price"], "budget": "Low"}
    saved = client.put("/me/profile", json=body, headers=user["headers"])
    assert saved.status_code == 200
    fetched = client.get("/me/profile", headers=user["headers"]).json()
    assert fetched["completed"] is True
    assert fetched["cuisines"] == ["Mexican", "Italian"]


def test_review_is_replaced_not_duplicated(client, make_user, db):
    user = make_user()
    path = "/restaurants/r1/reviews"
    assert client.post(path, json=REVIEW, headers=user["headers"]).status_code == 200
    updated = {**REVIEW, "taste": 1, "attention": 1, "price": 1, "options": 1}
    assert client.post(path, json=updated, headers=user["headers"]).status_code == 200
    assert db.query(func.count(models.Review.id)).scalar() == 1
    listing = client.get(path).json()
    assert listing["review_count"] == 1
    assert listing["rating"] == 1.0
    created = datetime.fromisoformat(listing["reviews"][0]["created_at"].replace("Z", "+00:00"))
    assert created.utcoffset().total_seconds() == 0


def test_review_summary_averages_users(client, make_user):
    first, second = make_user("Uno"), make_user("Dos")
    client.post("/restaurants/r1/reviews", json=REVIEW, headers=first["headers"])
    low = {**REVIEW, "taste": 1, "attention": 1, "price": 1, "options": 1}
    client.post("/restaurants/r1/reviews", json=low, headers=second["headers"])
    summary = {s["restaurant_id"]: s for s in client.get("/reviews/summary").json()}
    assert summary["r1"]["review_count"] == 2
    assert summary["r1"]["rating"] == 2.5


def test_occupancy_reports(client, make_user):
    first, second = make_user(), make_user()
    assert client.get("/occupancy/r9").json()["level"] is None
    client.post("/occupancy/reports", json={"restaurant_id": "r9", "level": 2}, headers=first["headers"])
    response = client.post("/occupancy/reports", json={"restaurant_id": "r9", "level": 0}, headers=second["headers"])
    assert response.status_code == 201
    assert response.json()["level"] == 1.0
    assert len(client.get("/occupancy").json()) == 1


def test_occupancy_events_and_rate(client, make_user):
    user = make_user()
    for event in ("occupancy_checked", "go_decision"):
        body = {"restaurant_id": "r1", "event": event, "has_data": True}
        assert client.post("/analytics/occupancy-event", json=body, headers=user["headers"]).status_code == 200
    summary = client.get("/analytics/occupancy-check-rate").json()
    assert summary["checks"] == 1
    assert summary["check_before_go_rate"] == 100.0


def test_weekly_app_opens_matches_sqlite_week_format(client, make_user, db):
    user = make_user()
    for slot in ("Lunch", "Lunch", "Dinner"):
        assert client.post("/analytics/app-open", json={"meal_slot": slot}, headers=user["headers"]).status_code == 200
    summary = client.get("/analytics/app-opens/weekly").json()
    assert summary["total_opens"] == 3
    assert summary["user_weeks"] == 1
    assert summary["average_opens_per_user_per_week"] == 3.0
    assert {m["meal_slot"]: m["count"] for m in summary["opens_by_meal_slot"]}["Lunch"] == 2
    export = client.get("/analytics/app-opens/export")
    week = db.query(models.AppOpen.timestamp).first()[0].strftime("%Y-%W")
    assert f"{user['id']},{week},3" in export.text


def test_anonymous_analytics_and_exports(client):
    assert client.post("/analytics/zero-result-search", json={"query": "sushi"}).status_code == 200
    client.post("/analytics/zero-result-search", json={"query": "sushi"})
    gaps = client.get("/analytics/search-gaps").json()
    assert gaps == [{"query": "sushi", "count": 2}]
    assert "sushi,2" in client.get("/analytics/search-gaps/export").text
    assert client.get("/analytics/onboarding-completion").status_code == 200
    assert client.get("/analytics/filter-usage").json() == []
    assert client.get("/analytics/saved-rarely-viewed").status_code == 200


def test_restaurant_view_flow(client, make_user):
    user = make_user()
    client.put("/me/saved/r1", headers=user["headers"])
    assert client.post("/analytics/restaurant-view", json={"restaurant_id": "r1"}, headers=user["headers"]).status_code == 200
    summary = client.get("/analytics/saved-rarely-viewed").json()
    assert summary["saves_analyzed"] == 1
