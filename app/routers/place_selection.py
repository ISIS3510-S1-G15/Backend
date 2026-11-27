# BQ Type 2 (Juan Felipe Ochoa): "How long does it take, on average, for a user to go from opening the app
# to selecting a place to eat?" Sprint 4 correction: the answer now ACTS for the user. If a student takes
# longer than the others to decide at this meal moment, /me/quick-pick gives the app a one-tap shortcut to
# the place they usually choose; /by-source then measures whether the shortcut reduced the decision time.
import csv
import io
from typing import get_args

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

# A place counts as "your usual" once you picked it this many times at the same meal moment.
MIN_PERSONAL_PICKS = 2
# Below this, a campus-wide favorite is just noise, so the app shows nothing.
MIN_CAMPUS_PICKS = 3
# How many restaurant ids we hand over; the app keeps the first one open now (it owns the schedules).
MAX_CANDIDATES = 3

Event = models.PlaceSelectionEvent
SECONDS = Event.ms_since_app_open / 1000.0
# Rows from before Sprint 4 have no source; they were all taps from the detail screen.
SOURCE = func.coalesce(Event.source, "detail")
UNAIDED = SOURCE == "detail"
SOURCES = get_args(schemas.SelectionSource)

_AGGREGATES = (
    func.count(),
    func.count(distinct(Event.user_id)),
    func.avg(SECONDS),
    func.percentile_cont(0.5).within_group(SECONDS),
    func.percentile_cont(0.9).within_group(SECONDS),
    func.count().filter(Event.ms_since_app_open <= 60_000),
    func.count().filter(Event.ms_since_app_open <= 300_000),
)


@router.post("/place-selection", response_model=schemas.PlaceSelectionLogged)
def log_place_selection(
    payload: schemas.PlaceSelectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(Event(
        user_id=current_user.id,
        restaurant_id=payload.restaurant_id,
        ms_since_app_open=payload.ms_since_app_open,
        meal_slot=payload.meal_slot,
        source=payload.source,
    ))
    db.commit()
    return {"saved": True}


def _stats(row) -> dict:
    selections, users, avg, median, p90, within_1min, within_5min = row
    pct = lambda n: round(n * 100 / selections, 1) if selections else None
    rnd = lambda v: round(float(v), 1) if v is not None else None
    return {
        "selections": selections,
        "users": users,
        "avg_seconds": rnd(avg),
        "median_seconds": rnd(median),
        "p90_seconds": rnd(p90),
        "within_1min_pct": pct(within_1min),
        "within_5min_pct": pct(within_5min),
    }


@router.get("/time-to-selection", response_model=schemas.TimeToSelectionSummary)
def get_time_to_selection(db: Session = Depends(get_db)):
    overall = db.execute(select(*_AGGREGATES).select_from(Event)).one()
    by_slot = db.execute(
        select(Event.meal_slot, *_AGGREGATES).group_by(Event.meal_slot).order_by(Event.meal_slot)
    ).all()
    return {
        "overall": _stats(overall),
        "by_meal_slot": [{"meal_slot": row[0], **_stats(row[1:])} for row in by_slot],
    }


@router.get("/time-to-selection/me", response_model=schemas.MyTimeToSelection)
def get_my_time_to_selection(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    campus_n, campus_avg = db.execute(select(func.count(), func.avg(SECONDS)).select_from(Event)).one()
    my_n, my_avg = db.execute(
        select(func.count(), func.avg(SECONDS)).select_from(Event).where(Event.user_id == current_user.id)
    ).one()
    rnd = lambda v: round(float(v), 1) if v is not None else None
    return {
        "campus_avg_seconds": rnd(campus_avg),
        "campus_selections": campus_n,
        "my_avg_seconds": rnd(my_avg),
        "my_selections": my_n,
    }


def _round(value) -> float | None:
    return round(float(value), 1) if value is not None else None


def _top_places(db: Session, *filters) -> list[tuple[str, int]]:
    # Most chosen first; on a tie, the most recently chosen wins.
    rows = db.execute(
        select(Event.restaurant_id, func.count())
        .where(*filters)
        .group_by(Event.restaurant_id)
        .order_by(func.count().desc(), func.max(Event.received_at).desc(), Event.restaurant_id)
        .limit(MAX_CANDIDATES)
    ).all()
    return [(restaurant_id, count) for restaurant_id, count in rows]


# Static path, declared before any parametrised route so it can never be shadowed.
@router.get("/time-to-selection/me/quick-pick", response_model=schemas.QuickPickOut)
def get_my_quick_pick(
    meal_slot: schemas.MealSlot = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    in_slot = Event.meal_slot == meal_slot
    mine = Event.user_id == current_user.id
    # Averages use unaided picks only, so using the shortcut does not hide the slowness that triggered it.
    my_n, my_avg = db.execute(select(func.count(), func.avg(SECONDS)).where(in_slot, mine, UNAIDED)).one()
    campus_avg = db.execute(select(func.avg(SECONDS)).where(in_slot, UNAIDED)).scalar()
    my_avg, campus_avg = _round(my_avg), _round(campus_avg)

    kind, places = None, []
    # The habit counts every pick, shortcut included: choosing it again confirms it is still the usual.
    personal = _top_places(db, in_slot, mine)
    if personal and personal[0][1] >= MIN_PERSONAL_PICKS:
        slow = my_avg is None or campus_avg is None or my_avg >= campus_avg
        if slow:
            kind, places = "your_usual", personal
        # Otherwise the user already decides faster than campus: no card needed.
    else:
        campus = _top_places(db, in_slot)
        if campus and campus[0][1] >= MIN_CAMPUS_PICKS:
            kind, places = "campus_favorite", campus

    # Only restaurant ids and aggregates leave this endpoint; never other users' data.
    return {
        "meal_slot": meal_slot,
        "kind": kind,
        "candidates": [restaurant_id for restaurant_id, _ in places],
        "times_chosen": places[0][1] if places else 0,
        "my_avg_seconds": my_avg,
        "campus_avg_seconds": campus_avg,
        "my_selections": my_n,
    }


@router.get("/time-to-selection/by-source", response_model=schemas.TimeToSelectionBySource)
def get_time_to_selection_by_source(db: Session = Depends(get_db)):
    rows = {row[0]: row[1:] for row in db.execute(select(SOURCE, *_AGGREGATES).group_by(SOURCE)).all()}
    # Always both rows, so the dashboard can compare even before anyone used the shortcut.
    empty = (0, 0, None, None, None, 0, 0)
    by_source = [{"source": source, **_stats(rows.get(source, empty))} for source in SOURCES]
    total = sum(item["selections"] for item in by_source)
    quick = next(item["selections"] for item in by_source if item["source"] == "quick_pick")
    return {
        "by_source": by_source,
        "quick_pick_share_pct": round(quick * 100 / total, 1) if total else None,
    }


@router.get("/time-to-selection/export")
def export_time_to_selection(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Event.user_id, Event.restaurant_id, Event.meal_slot, Event.ms_since_app_open, Event.received_at, SOURCE)
        .order_by(Event.received_at)
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "restaurant_id", "meal_slot", "seconds_since_app_open", "received_at_utc", "source"])
    for user_id, restaurant_id, meal_slot, ms, received_at, source in rows:
        writer.writerow([user_id, restaurant_id, meal_slot or "", round(ms / 1000, 1), received_at.isoformat(), source])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=time_to_selection_report.csv"},
    )
