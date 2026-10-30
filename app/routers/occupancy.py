# Reportes de ocupación "en tiempo real" (Juan Felipe Ochoa)
# Antes: crowdingReports fijo en cada restaurante (Home y Mapa) + SharedPreferences solo en el celular de quien
# reportaba (Detalle). Ahora todos los usuarios y todas las pantallas leen el mismo dato desde aquí
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/occupancy", tags=["occupancy"])

RECENT_WINDOW = timedelta(hours=1)  # un reporte de hace más de 1 hora ya no dice cómo está el lugar AHORA
MAX_REPORTS = 10                    # el indicador usa como máximo los 10 reportes más nuevos


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # UTC sin zona, como se guarda en SQLite


def occupancy_status(db: Session, restaurant_ids: list[str] | None = None) -> dict[str, dict]:
    """Estado actual de ocupación por restaurante: reportes de la última hora, solo el más nuevo de cada usuario
    (así alguien que toca "Busy" 5 veces no pesa 5 veces), máximo MAX_REPORTS, y su promedio 0-2."""
    query = db.query(models.OccupancyReport).filter(models.OccupancyReport.created_at >= _now() - RECENT_WINDOW)
    if restaurant_ids is not None:
        query = query.filter(models.OccupancyReport.restaurant_id.in_(restaurant_ids))
    rows = query.order_by(models.OccupancyReport.created_at.desc(), models.OccupancyReport.id.desc()).all()

    result: dict[str, dict] = {}
    seen: set[tuple[str, int]] = set()  # (restaurante, usuario) ya contados
    for report in rows:  # vienen del más nuevo al más viejo
        key = (report.restaurant_id, report.user_id)
        if key in seen:
            continue
        seen.add(key)
        entry = result.setdefault(report.restaurant_id, {
            "restaurant_id": report.restaurant_id,
            "reports": [],
            "last_report_at": report.created_at.replace(tzinfo=timezone.utc),
            "last_report_id": report.id,
        })
        if len(entry["reports"]) < MAX_REPORTS:
            entry["reports"].append(report.level)

    for entry in result.values():
        entry["level"] = round(sum(entry["reports"]) / len(entry["reports"]), 2)
    return result


def _status_for(db: Session, restaurant_id: str) -> dict:
    empty = {"restaurant_id": restaurant_id, "level": None, "reports": [], "last_report_at": None, "last_report_id": None}
    return occupancy_status(db, [restaurant_id]).get(restaurant_id, empty)


# Estado de todos los restaurantes con reportes recientes (badges de Home, Mapa, Search y Saved en UNA petición)
@router.get("", response_model=list[schemas.OccupancyOut])
def get_all_occupancy(db: Session = Depends(get_db)):
    return list(occupancy_status(db).values())


# Guarda un reporte con el usuario del token y la hora del servidor (no la del celular, que puede estar mal)
# y devuelve el estado ya actualizado, para que la app no tenga que hacer otra petición
@router.post("/reports", response_model=schemas.OccupancyOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: schemas.OccupancyReportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(models.OccupancyReport(
        restaurant_id=payload.restaurant_id,
        user_id=current_user.id,
        level=payload.level,
        created_at=func.timezone("UTC", func.now()),
    ))
    db.commit()
    return _status_for(db, payload.restaurant_id)


# Estado de un restaurante (tarjeta del Detalle, que lo vuelve a pedir cada cierto tiempo mientras está abierta)
@router.get("/{restaurant_id}", response_model=schemas.OccupancyOut)
def get_occupancy(restaurant_id: str, db: Session = Depends(get_db)):
    return _status_for(db, restaurant_id)
