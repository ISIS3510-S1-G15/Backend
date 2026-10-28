def _plain(group, values, start=0):
    return [
        {"group_key": group, "value": value, "label": value, "detail": None, "emoji": None, "extra": None, "sort_order": start + index}
        for index, value in enumerate(values)
    ]


def _detailed(group, rows):
    return [
        {"group_key": group, "value": value, "label": label, "detail": detail, "emoji": emoji, "extra": None, "sort_order": index}
        for index, (value, label, detail, emoji) in enumerate(rows)
    ]


def _with_extra(group, rows):
    return [
        {"group_key": group, "value": value, "label": value, "detail": None, "emoji": None,
         "extra": extra, "sort_order": index}
        for index, (value, extra) in enumerate(rows)
    ]


CATALOG_SEED = (
    _plain("survey_cuisines", [
        "Colombian", "Mediterranean", "Asian", "American", "Mexican",
        "Italian", "Indian", "Middle Eastern", "Vegetarian", "Vegan",
    ])
    + _plain("survey_dietary", [
        "None", "Vegetarian", "Vegan", "Gluten-free", "Lactose-free", "Halal", "Kosher", "Nut-free",
    ])
    + _plain("survey_frequencies", ["Daily", "4–5x / week", "2–3x / week", "Once a week"])
    + _plain("survey_priorities", [
        "Price", "Speed", "Nutrition", "Taste", "Variety", "Proximity", "Sustainability",
    ])
    + _detailed("survey_budgets", [
        ("Under $8.000", "Under $8.000", "Looking for the best deals", "💸"),
        ("$8.000 – $15.000", "$8.000 – $15.000", "Mid-range, good value", "💵"),
        ("$15.000 – $25.000", "$15.000 – $25.000", "Happy to spend a bit more", "🪙"),
        ("Over $25.000", "Over $25.000", "Quality is top priority", "💎"),
    ])
    + _plain("review_dietary_options", [
        "Vegan options", "Vegetarian options", "Gluten-free", "Lactose-free", "Nut-free", "Halal", "Kosher",
    ])
    + _plain("saved_dietary_filters", ["Vegan", "Gluten-free", "Halal", "Vegetarian"])
    + _plain("filter_prices", ["$", "$$", "$$$"])
    + [
        {"group_key": "filter_ratings", "value": "0.0", "label": "Any", "detail": None, "emoji": None, "extra": None, "sort_order": 0},
        {"group_key": "filter_ratings", "value": "4.0", "label": "4.0+", "detail": None, "emoji": None, "extra": None, "sort_order": 1},
        {"group_key": "filter_ratings", "value": "4.5", "label": "4.5+", "detail": None, "emoji": None, "extra": None, "sort_order": 2},
    ]
    + _detailed("crowding_levels", [
        ("1", "Empty", "Plenty of seats", "🪑"),
        ("2", "Quiet", "Few people around", "😌"),
        ("3", "Moderate", "Some tables taken", "🙂"),
        ("4", "Busy", "Hard to find a seat", "😅"),
        ("5", "Packed", "Completely full", "😬"),
    ])
    + _detailed("review_categories", [
        ("taste", "Taste & Food Quality", "Taste", None),
        ("attention", "Service & Attention", "Service", None),
        ("price", "Value for Money", "Value", None),
        ("options", "Dietary Options", "Diet Options", None),
    ])
    + [
        {"group_key": "review_rating_words", "value": str(index + 1), "label": word,
         "detail": None, "emoji": None, "extra": None, "sort_order": index}
        for index, word in enumerate(["Poor", "Fair", "Good", "Great", "Excellent"])
    ]
    + _with_extra("meal_slots", [
        ("Breakfast", {"start_hour": 5, "end_hour": 8}),
        ("Mid-morning snack", {"start_hour": 9, "end_hour": 10}),
        ("Lunch", {"start_hour": 11, "end_hour": 14}),
        ("Afternoon snack", {"start_hour": 15, "end_hour": 17}),
        ("Dinner", {"start_hour": 18, "end_hour": 21}),
        ("Late night", {"fallback": True}),
    ])
    + _with_extra("meal_moments", [
        ("Breakfast", {"start_hour": 6, "end_hour": 10, "categories": ["Café", "Smoothies", "Dining Hall"]}),
        ("Lunch", {"start_hour": 11, "end_hour": 14, "categories": ["Dining Hall", "Asian", "Burgers", "Indian"]}),
        ("Snack", {"start_hour": 15, "end_hour": 17, "categories": ["Café", "Smoothies"]}),
        ("Dinner", {"start_hour": 18, "end_hour": 21, "categories": ["Asian", "Burgers", "Indian", "Dining Hall"]}),
    ])
    + _with_extra("campus_location", [
        ("latitude", {"number": 4.6018}),
        ("longitude", {"number": -74.0661}),
        ("radius_meters", {"number": 600}),
        ("walking_meters_per_minute", {"number": 80}),
    ])
)
