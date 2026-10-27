# BQ Type 3: "What places are saved as favorites but rarely viewed in detail again?"
#   1. Captura:        la app manda una vista cada vez que se abre el detalle de un restaurante
#                      (POST /analytics/restaurant-view); los guardados ya están en saved_restaurants
#   2. Almacenamiento: tabla restaurant_views (usuario del token, restaurante, hora)
#   3. Procesamiento:  por cada restaurante guardado, cuántas veces lo volvió a abrir ese usuario DESPUÉS de guardarlo
#                      (GET /analytics/saved-rarely-viewed)
#   4. Reporte:        GET /analytics/saved-rarely-viewed/export (CSV, una fila por guardado)
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _naive_utc(dt: datetime) -> datetime:
    # SQLite devuelve las fechas sin zona horaria (en UTC): así se pueden comparar todas
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


# Se llama cada vez que el usuario abre el detalle de un restaurante
@router.post("/restaurant-view", response_model=schemas.RestaurantViewLogged)
def log_restaurant_view(
    payload: schemas.RestaurantViewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(models.RestaurantView(user_id=current_user.id, restaurant_id=payload.restaurant_id))
    db.commit()
    return {"saved": True}


def _saves_with_views(db: Session, min_days_saved: int) -> list[dict]:
    # Cada guardado (usuario, restaurante) con cuántas veces ese usuario abrió el detalle después de guardarlo
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=min_days_saved)
    views = defaultdict(list)  # (usuario, restaurante) -> horas de sus vistas
    for v in db.query(models.RestaurantView).all():
        views[(v.user_id, v.restaurant_id)].append(_naive_utc(v.viewed_at))

    result = []
    for s in db.query(models.SavedRestaurant).all():
        saved_at = _naive_utc(s.saved_at)
        if saved_at > cutoff:
            continue  # guardado muy reciente: todavía no tuvo tiempo de volver a verlo
        after = sum(1 for t in views[(s.user_id, s.restaurant_id)] if t > saved_at)
        result.append({"user_id": s.user_id, "restaurant_id": s.restaurant_id,
                       "saved_at": saved_at, "views_after_saving": after})
    return result


@router.get("/saved-rarely-viewed", response_model=schemas.SavedRarelyViewedSummary)
def get_saved_rarely_viewed(
    max_views: int = Query(1, ge=0, description="'Rarely' = esta cantidad de vistas o menos después de guardar"),
    min_days_saved: int = Query(0, ge=0, description="Ignora guardados más nuevos que esto (en días)"),
    db: Session = Depends(get_db),
):
    saves = _saves_with_views(db, min_days_saved)
    per_place = defaultdict(list)
    for s in saves:
        per_place[s["restaurant_id"]].append(s["views_after_saving"])

    places = []
    for rid, counts in per_place.items():
        rarely = sum(1 for c in counts if c <= max_views)
        places.append({
            "restaurant_id": rid,
            "times_saved": len(counts),
            "rarely_viewed": rarely,
            "rarely_viewed_pct": round(rarely * 100 / len(counts), 1),
            "avg_views_after_saving": round(sum(counts) / len(counts), 1),
        })
    places.sort(key=lambda p: (-p["rarely_viewed_pct"], -p["times_saved"]))

    total_rarely = sum(p["rarely_viewed"] for p in places)
    return {
        "max_views": max_views,
        "min_days_saved": min_days_saved,
        "saves_analyzed": len(saves),
        "rarely_viewed": total_rarely,
        "rarely_viewed_pct": round(total_rarely * 100 / len(saves), 1) if saves else 0.0,
        "places": places,
    }


# Versión CSV: una fila por guardado, con cuántas veces se volvió a ver
@router.get("/saved-rarely-viewed/export")
def export_saved_rarely_viewed(min_days_saved: int = Query(0, ge=0), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["restaurant_id", "user_id", "saved_at_utc", "views_after_saving"])  # header row
    for s in _saves_with_views(db, min_days_saved):
        writer.writerow([s["restaurant_id"], s["user_id"], s["saved_at"].isoformat(), s["views_after_saving"]])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=saved_rarely_viewed_report.csv"},
    )
