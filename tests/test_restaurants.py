from app import models


def test_list_returns_seeded_restaurants(client, db):
    response = client.get("/restaurants")
    assert response.status_code == 200
    body = response.json()["restaurants"]
    assert [r["id"] for r in body] == ["1", "2", "3", "4"]
    assert body[0]["name"] == "Starbucks"
    assert body[0]["image_key"] == "starbucks"
    assert body[3]["image_url"].startswith("https://")
    assert body[0]["menu"][0]["items"][0]["name"] == "Oat Latte"
    assert db.query(models.Restaurant).count() == 4


def test_get_one_and_missing(client):
    assert client.get("/restaurants/2").json()["name"] == "Kai Sushi"
    assert client.get("/restaurants/999").status_code == 404
