import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import distinct, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.routers.occupancy import RECENT_WINDOW
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

Event = models.OccupancyPropagationEvent
Report = models.OccupancyReport

SECONDS = func.extract("epoch", Event.seen_at - Report.created_at)


def _db_now(db: Session):
    return db.scalar(select(func.timezone("UTC", func.now())))


def _report_of(db: Session, report_id: int, restaurant_id: str) -> models.OccupancyReport | None:
    report = db.get(Report, report_id)
    return report if report is not None and report.restaurant_id == restaurant_id else None


@router.post("/occupancy-propagation", response_model=schemas.OccupancyPropagationLogged)
def log_propagation(
    payload: schemas.OccupancyPropagationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current = _report_of(db, payload.report_id, payload.restaurant_id)
    if current is None:
        raise HTTPException(404, "Report not found for this restaurant")

    lower = _db_now(db) - RECENT_WINDOW
    if payload.previous_report_id is not None:
        previous = _report_of(db, payload.previous_report_id, payload.restaurant_id)
        if previous is None:
            raise HTTPException(422, "previous_report_id is not from this restaurant")
        lower = max(lower, previous.created_at)

    new_ids = db.scalars(
        select(Report.id).where(
            Report.restaurant_id == payload.restaurant_id,
            Report.created_at > lower,
            Report.created_at <= current.created_at,
            Report.user_id != current_user.id,
        )
    ).all()
    if not new_ids:
        return {"saved": 0}

    result = db.execute(
        postgres_insert(Event)
        .values([
            {
                "report_id": report_id,
                "user_id": current_user.id,
                "source": payload.source,
                "ms_since_previous_refresh": payload.ms_since_previous_refresh,
            }
            for report_id in new_ids
        ])
        .on_conflict_do_nothing(constraint="uq_propagation_user_report")
        .returning(Event.id)
    )
    saved = len(result.all())
    db.commit()
    return {"saved": saved}


def _stats(row) -> dict:
    updates, reports, avg, median, p90, within_30s, within_5min = row
    pct = lambda n: round(n * 100 / updates, 1) if updates else None
    rnd = lambda v: round(float(v), 1) if v is not None else None
    return {
        "updates": updates,
        "reports": reports,
        "avg_seconds": rnd(avg),
        "median_seconds": rnd(median),
        "p90_seconds": rnd(p90),
        "within_30s_pct": pct(within_30s),
        "within_5min_pct": pct(within_5min),
    }


_AGGREGATES = (
    func.count(),
    func.count(distinct(Event.report_id)),
    func.avg(SECONDS),
    func.percentile_cont(0.5).within_group(SECONDS),
    func.percentile_cont(0.9).within_group(SECONDS),
    func.count().filter(SECONDS <= 30),
    func.count().filter(SECONDS <= 300),
)


@router.get("/occupancy-propagation", response_model=schemas.OccupancyPropagationSummary)
def get_propagation_summary(db: Session = Depends(get_db)):
    overall = db.execute(
        select(*_AGGREGATES).select_from(Event).join(Report, Report.id == Event.report_id)
    ).one()
    by_source = db.execute(
        select(Event.source, *_AGGREGATES)
        .select_from(Event)
        .join(Report, Report.id == Event.report_id)
        .group_by(Event.source)
        .order_by(Event.source)
    ).all()
    return {
        "overall": _stats(overall),
        "by_source": [{"source": row[0], **_stats(row[1:])} for row in by_source],
    }


@router.get("/occupancy-propagation/export")
def export_propagation(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Event.report_id, Report.restaurant_id, Event.source, Report.created_at, Event.seen_at,
            SECONDS, Event.ms_since_previous_refresh,
        )
        .join(Report, Report.id == Event.report_id)
        .order_by(Event.seen_at)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "report_id", "restaurant_id", "source", "reported_at_utc", "seen_at_utc", "seconds",
        "ms_since_previous_refresh",
    ])
    for report_id, restaurant_id, source, reported_at, seen_at, seconds, gap in rows:
        writer.writerow([
            report_id, restaurant_id, source, reported_at.isoformat(), seen_at.isoformat(),
            round(float(seconds), 1), "" if gap is None else gap,
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=occupancy_propagation_report.csv"},
    )
