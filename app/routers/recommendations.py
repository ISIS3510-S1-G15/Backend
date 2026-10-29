import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

DECISION_WINDOW = timedelta(minutes=30)
LEVELS = ("not_crowded", "moderate", "busy", "no_data")


def occupancy_level(level: float | None) -> str:
    if level is None:
        return "no_data"
    if level < 0.7:
        return "not_crowded"
    if level < 1.4:
        return "moderate"
    return "busy"


@router.post("/recommendation-shown", response_model=schemas.RecommendationShownLogged)
def log_recommendation_shown(
    payload: schemas.RecommendationShownCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(models.RecommendationEvent(
        user_id=current_user.id,
        recommended_id=payload.recommended_id,
        recommended_level=payload.recommended_level,
        occupancy_level=occupancy_level(payload.recommended_level),
        alternative_id=payload.alternative_id,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    return {"saved": True}


def _outcomes(db: Session) -> list[dict]:
    recommendations = db.query(models.RecommendationEvent).order_by(models.RecommendationEvent.timestamp).all()
    decisions = (
        db.query(models.OccupancyEvent)
        .filter(models.OccupancyEvent.event == "go_decision")
        .order_by(models.OccupancyEvent.timestamp)
        .all()
    )

    latest_shown: dict[int, list[models.RecommendationEvent]] = {}
    for rec in recommendations:
        latest_shown.setdefault(rec.user_id, []).append(rec)

    outcomes = []
    for decision in decisions:
        shown_before = [
            rec for rec in latest_shown.get(decision.user_id, [])
            if rec.timestamp <= decision.timestamp <= rec.timestamp + DECISION_WINDOW
        ]
        if not shown_before:
            continue
        rec = shown_before[-1]
        if decision.restaurant_id == rec.recommended_id:
            choice = "recommended"
        elif decision.restaurant_id == rec.alternative_id:
            choice = "suggested_alternative"
        else:
            choice = "other_place"
        outcomes.append({
            "user_id": decision.user_id,
            "recommended_id": rec.recommended_id,
            "occupancy_level": rec.occupancy_level,
            "alternative_id": rec.alternative_id,
            "chosen_id": decision.restaurant_id,
            "choice": choice,
            "decided_at": decision.timestamp,
        })
    return outcomes


def _rate(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total else 0.0


def _summary(db: Session) -> dict:
    shown_by_level = {level: 0 for level in LEVELS}
    for (level,) in db.query(models.RecommendationEvent.occupancy_level).all():
        shown_by_level[level] = shown_by_level.get(level, 0) + 1

    outcomes = _outcomes(db)
    by_level = []
    for level in LEVELS:
        rows = [o for o in outcomes if o["occupancy_level"] == level]
        counts = {c: sum(1 for o in rows if o["choice"] == c) for c in ("recommended", "suggested_alternative", "other_place")}
        by_level.append({
            "occupancy_level": level,
            "recommendations": shown_by_level.get(level, 0),
            "decisions": len(rows),
            "chose_recommended": counts["recommended"],
            "chose_suggested_alternative": counts["suggested_alternative"],
            "chose_other_place": counts["other_place"],
            "alternative_rate": _rate(len(rows) - counts["recommended"], len(rows)),
        })

    alternatives = sum(1 for o in outcomes if o["choice"] != "recommended")
    return {
        "recommendations": sum(shown_by_level.values()),
        "decisions": len(outcomes),
        "alternative_rate": _rate(alternatives, len(outcomes)),
        "by_level": by_level,
    }


@router.get("/occupancy-alternatives", response_model=schemas.OccupancyAlternativesSummary)
def get_occupancy_alternatives(db: Session = Depends(get_db)):
    return _summary(db)


@router.get("/occupancy-alternatives/export")
def export_occupancy_alternatives(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "recommended_id", "occupancy_level", "alternative_id", "chosen_id", "choice", "decided_at_utc"])
    for o in _outcomes(db):
        writer.writerow([
            o["user_id"], o["recommended_id"], o["occupancy_level"], o["alternative_id"] or "",
            o["chosen_id"], o["choice"], o["decided_at"].isoformat(),
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=occupancy_alternatives_report.csv"},
    )
