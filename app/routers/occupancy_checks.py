# BQ: "How often do users check or inquire about a restaurant's occupancy level before deciding to go?"
#   1. Captura:        el detalle del restaurante manda "occupancy_checked" al mostrar el indicador
#                      y "go_decision" cuando el usuario toca "Get directions" (POST /analytics/occupancy-event)
#   2. Almacenamiento: una fila por evento con el usuario (sale del token), el restaurante y la hora del servidor
#   3. Procesamiento:  GET /analytics/occupancy-check-rate -> % de decisiones de ir que tuvieron una revisión
#                      de la ocupación en los 30 minutos previos, y revisiones promedio por usuario por semana
#   4. Reporte:        GET /analytics/occupancy-check-rate/export (CSV)
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

CHECK_WINDOW = timedelta(minutes=30)  # una revisión cuenta si pasó hasta 30 min antes de decidir ir


@router.post("/occupancy-event", response_model=schemas.OccupancyEventLogged)
def log_occupancy_event(
    payload: schemas.OccupancyEventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(models.OccupancyEvent(
        user_id=current_user.id,
        restaurant_id=payload.restaurant_id,
        event=payload.event,
        has_data=payload.has_data if payload.event == "occupancy_checked" else None,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.commit()
    return {"saved": True}


def _decisions(db: Session) -> list[dict]:
    # Cada "go_decision" con un indicador de si hubo una revisión del mismo usuario y lugar en los 30 min previos
    events = db.query(models.OccupancyEvent).order_by(models.OccupancyEvent.timestamp).all()
    checks = defaultdict(list)  # (usuario, restaurante) -> horas de sus revisiones
    result = []
    for e in events:
        key = (e.user_id, e.restaurant_id)
        if e.event == "occupancy_checked":
            checks[key].append(e.timestamp)
        elif e.event == "go_decision":
            checked = any(e.timestamp - CHECK_WINDOW <= t <= e.timestamp for t in checks[key])
            result.append({"restaurant_id": e.restaurant_id, "user_id": e.user_id,
                           "timestamp": e.timestamp, "checked_before": checked})
    return result


def _summary(db: Session) -> dict:
    checks = db.query(models.OccupancyEvent).filter(models.OccupancyEvent.event == "occupancy_checked").all()
    decisions = _decisions(db)
    after_check = sum(d["checked_before"] for d in decisions)

    # Revisiones por usuario por semana (solo cuentan las semanas en que ese usuario revisó algo)
    per_user_week = defaultdict(int)
    for c in checks:
        per_user_week[(c.user_id, c.timestamp.isocalendar()[:2])] += 1

    by_restaurant = defaultdict(lambda: {"checks": 0, "go_decisions": 0, "decisions_after_check": 0})
    for c in checks:
        by_restaurant[c.restaurant_id]["checks"] += 1
    for d in decisions:
        by_restaurant[d["restaurant_id"]]["go_decisions"] += 1
        by_restaurant[d["restaurant_id"]]["decisions_after_check"] += d["checked_before"]

    return {
        "checks": len(checks),
        "checks_without_data": sum(1 for c in checks if c.has_data is False),
        "go_decisions": len(decisions),
        "decisions_after_check": after_check,
        "check_before_go_rate": round(after_check * 100 / len(decisions), 1) if decisions else 0.0,
        "avg_checks_per_user_per_week": (
            round(sum(per_user_week.values()) / len(per_user_week), 1) if per_user_week else 0.0
        ),
        "by_restaurant": [
            {"restaurant_id": rid, **counts}
            for rid, counts in sorted(by_restaurant.items(), key=lambda kv: -kv[1]["checks"])
        ],
    }


@router.get("/occupancy-check-rate", response_model=schemas.OccupancyCheckRateSummary)
def get_occupancy_check_rate(db: Session = Depends(get_db)):
    return _summary(db)


# Versión CSV: una fila por decisión de ir, diciendo si revisó la ocupación antes
@router.get("/occupancy-check-rate/export")
def export_occupancy_check_rate(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["restaurant_id", "user_id", "decided_at_utc", "checked_occupancy_before"])  # header row
    for d in _decisions(db):
        writer.writerow([d["restaurant_id"], d["user_id"], d["timestamp"].isoformat(), d["checked_before"]])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=occupancy_check_report.csv"},
    )
