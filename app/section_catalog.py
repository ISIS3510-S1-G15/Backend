from typing import Literal

SectionName = Literal["map", "filters", "details", "favorites"]
SectionEventType = Literal["section_view", "section_interaction"]

SECTIONS = ("map", "filters", "details", "favorites")

SECTION_VIEW = "section_view"
SECTION_INTERACTION = "section_interaction"

ALLOWED_ACTIONS = {
    "map": frozenset({"marker_selected", "restaurant_selected", "filter_chip_changed"}),
    "filters": frozenset({"filters_applied", "filters_cleared"}),
    "details": frozenset({"directions_opened", "reviews_opened", "review_write_opened"}),
    "favorites": frozenset({"favorite_added", "favorite_removed", "saved_item_selected"}),
}

MIN_VISITS_PER_SECTION = 30
LOW_USE_RATIO = 0.5
MAX_BATCH_SIZE = 50
MAX_EXTRA_KEYS = 5
MAX_EXTRA_BYTES = 256
MAX_EVENT_AGE_DAYS = 7
MAX_FUTURE_SKEW_MINUTES = 5
