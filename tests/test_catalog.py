def test_catalog_returns_ordered_groups(client):
    response = client.get("/catalog")
    assert response.status_code == 200
    groups = response.json()["groups"]
    assert {
        "survey_cuisines", "survey_dietary", "meal_slots", "meal_moments", "campus_location", "survey_frequencies",
        "survey_priorities", "survey_budgets", "review_dietary_options", "saved_dietary_filters",
        "filter_prices", "filter_ratings", "crowding_levels", "review_categories", "review_rating_words",
    } <= set(groups)
    assert [o["value"] for o in groups["filter_prices"]] == ["$", "$$", "$$$"]
    assert [o["label"] for o in groups["crowding_levels"]] == ["Empty", "Quiet", "Moderate", "Busy", "Packed"]
    assert groups["survey_budgets"][0]["detail"] == "Looking for the best deals"
    assert groups["review_categories"][0] == {
        "value": "taste", "label": "Taste & Food Quality", "detail": "Taste", "emoji": None, "extra": None,
    }
    slots = {o["value"]: o["extra"] for o in groups["meal_slots"]}
    assert slots["Lunch"] == {"start_hour": 11, "end_hour": 14}
    assert slots["Late night"] == {"fallback": True}
    moments = {o["value"]: o["extra"] for o in groups["meal_moments"]}
    assert "Asian" in moments["Lunch"]["categories"]
    campus = {o["value"]: o["extra"]["number"] for o in groups["campus_location"]}
    assert campus["radius_meters"] == 600



def test_catalog_is_public(client):
    assert client.get("/catalog").status_code == 200
