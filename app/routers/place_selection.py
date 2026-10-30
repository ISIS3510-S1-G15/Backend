import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

Event = models.PlaceSelectionEvent
SECONDS = Event.ms_since_app_open / 1000.0

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


@router.get("/time-to-selection/export")
def export_time_to_selection(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Event.user_id, Event.restaurant_id, Event.meal_slot, Event.ms_since_app_open, Event.received_at)
        .order_by(Event.received_at)
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "restaurant_id", "meal_slot", "seconds_since_app_open", "received_at_utc"])
    for user_id, restaurant_id, meal_slot, ms, received_at in rows:
        writer.writerow([user_id, restaurant_id, meal_slot or "", round(ms / 1000, 1), received_at.isoformat()])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=time_to_selection_report.csv"},
    )
