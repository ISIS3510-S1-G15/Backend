from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models, schemas
import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

#cuando alguien haga un POST a /analytics/zero-result-search enviando un query, crea una fila nueva en la tabla, guárdala, y devuelve confirmación
@router.post("/zero-result-search", response_model=schemas.ZeroResultSearchOut)
def log_zero_result_search(payload: schemas.ZeroResultSearchCreate, db: Session = Depends(get_db)):
    entry = models.ZeroResultSearch(query=payload.query)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# Type 3 BQ: "What categories of food or restaurants do users search for
# without getting any results (gaps in the listed offerings)?"
@router.get("/search-gaps", response_model=list[schemas.SearchGapSummary])
def get_search_gaps(db: Session = Depends(get_db)):
    results = (
        db.query(
            models.ZeroResultSearch.query,
            func.count(models.ZeroResultSearch.id).label("count"),
        )
        .group_by(models.ZeroResultSearch.query)
        .order_by(func.count(models.ZeroResultSearch.id).desc())
        .all()
    )
    return [{"query": r.query, "count": r.count} for r in results]
# cuando alguien haga un GET a /analytics/search-gaps, cuenta cuántas veces se repite cada término buscado, y devuélvelos ordenados de más a menos frecuente.

# Downloadable CSV version of the search gaps report —
# useful for the wiki, the demo, and the Viva Voce
@router.get("/search-gaps/export")
def export_search_gaps(db: Session = Depends(get_db)):
    results = (
        db.query(
            models.ZeroResultSearch.query,
            func.count(models.ZeroResultSearch.id).label("count"),
        )
        .group_by(models.ZeroResultSearch.query)
        .order_by(func.count(models.ZeroResultSearch.id).desc())
        .all()
    )

    # Build the CSV content in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["query", "count"])  # header row
    for r in results:
        writer.writerow([r.query, r.count])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=search_gaps_report.csv"},
    )



#cuando alguien haga un POST a /analytics/onboarding-event, guarda el evento de la encuesta
@router.post("/onboarding-event", response_model=schemas.OnboardingEventOut)
def log_onboarding_event(payload: schemas.OnboardingEventCreate, db: Session = Depends(get_db)):
    entry = models.OnboardingEvent(session_id=payload.session_id, event=payload.event, step=payload.step)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# Type 2 BQ: "What percentage of users complete the food preferences survey
# during onboarding?"
def _onboarding_summary(db: Session):
    def sessions_with(event):
        return (
            db.query(func.count(func.distinct(models.OnboardingEvent.session_id)))
            .filter(models.OnboardingEvent.event == event)
            .scalar()
        )

    started = sessions_with("started")
    completed = sessions_with("completed")

    # el paso más lejano al que llegó cada sesión
    furthest = (
        db.query(
            models.OnboardingEvent.session_id,
            func.max(models.OnboardingEvent.step).label("max_step"),
        )
        .group_by(models.OnboardingEvent.session_id)
        .subquery()
    )
    max_step = db.query(func.max(furthest.c.max_step)).scalar() or 0
    reached = [
        {
            "step": step,
            "sessions": db.query(func.count()).select_from(furthest).filter(furthest.c.max_step >= step).scalar(),
        }
        for step in range(1, max_step + 1)
    ]

    rate = round(completed * 100 / started, 1) if started else 0.0
    return {"started": started, "completed": completed, "completion_rate": rate, "reached_by_step": reached}

# cuando alguien haga un GET a /analytics/onboarding-completion, calcula el porcentaje de encuestas completadas
@router.get("/onboarding-completion", response_model=schemas.OnboardingCompletionSummary)
def get_onboarding_completion(db: Session = Depends(get_db)):
    return _onboarding_summary(db)

# Versión CSV descargable: cuántas sesiones llegaron a cada paso
@router.get("/onboarding-completion/export")
def export_onboarding_completion(db: Session = Depends(get_db)):
    summary = _onboarding_summary(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["step", "sessions"])  # header row
    for r in summary["reached_by_step"]:
        writer.writerow([r["step"], r["sessions"]])
    writer.writerow(["completed", summary["completed"]])
    writer.writerow(["completion_rate_%", summary["completion_rate"]])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=onboarding_completion_report.csv"},
    )



#cuando alguien haga un POST a /analytics/filter-usage enviando filter y screen, guarda una fila nueva en la tabla
@router.post("/filter-usage", response_model=schemas.FilterUsageOut)
def log_filter_usage(payload: schemas.FilterUsageCreate, db: Session = Depends(get_db)):
    entry = models.FilterUsage(filter=payload.filter, screen=payload.screen)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# Type 2 BQ: "Which filters (diet, budget, distance, available time) are most
# commonly used when searching for a place to eat?"
def _filter_usage_summary(db: Session):
    return (
        db.query(
            models.FilterUsage.filter,
            models.FilterUsage.screen,
            func.count(models.FilterUsage.id).label("count"),
        )
        .group_by(models.FilterUsage.filter, models.FilterUsage.screen)
        .order_by(func.count(models.FilterUsage.id).desc())
        .all()
    )

# cuando alguien haga un GET a /analytics/filter-usage, cuenta cuántas veces se usó cada filtro y los ordena de más a menos usado
@router.get("/filter-usage", response_model=list[schemas.FilterUsageSummary])
def get_filter_usage(db: Session = Depends(get_db)):
    return [{"filter": r.filter, "screen": r.screen, "count": r.count} for r in _filter_usage_summary(db)]

# Versión CSV descargable del reporte de uso de filtros
@router.get("/filter-usage/export")
def export_filter_usage(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["filter", "screen", "count"])  # header row
    for r in _filter_usage_summary(db):
        writer.writerow([r.filter, r.screen, r.count])
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=filter_usage_report.csv"},
    )

    
# http://127.0.0.1:8000/docs#/analytics/get_search_gaps_analytics_search_gaps_get
# http://127.0.0.1:8000/docs


# =====================================================================
# Type 1 BQ (Juan Felipe Ochoa):
# "On average, how many times does a user open the app during a
#  typical academic week?"
# Solo usuarios autenticados: así una apertura se atribuye a una persona
# (y no a un celular), y el promedio por usuario es correcto.
# =====================================================================
from app.security import get_current_user

MEAL_SLOTS = ["Breakfast", "Mid-morning snack", "Lunch", "Afternoon snack", "Dinner", "Late night"]


# La app lo llama al iniciar sesión, al restaurar la sesión y cada vez que vuelve del segundo plano
@router.post("/app-open", response_model=schemas.AppOpenLogged)
def log_app_open(
    payload: schemas.AppOpenCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db.add(models.AppOpen(user_id=current_user.id, meal_slot=payload.meal_slot))
    db.commit()
    return {"saved": True}


def _weekly_opens_summary(db: Session) -> dict:
    # Cuántas aperturas tuvo cada usuario en cada semana del año (semana ISO aproximada con %Y-%W de SQLite)
    week = func.strftime("%Y-%W", models.AppOpen.timestamp)
    per_user_week = (
        db.query(models.AppOpen.user_id, week.label("week"), func.count(models.AppOpen.id).label("opens"))
        .group_by(models.AppOpen.user_id, week)
        .all()
    )
    total_opens = sum(row.opens for row in per_user_week)
    user_weeks = len(per_user_week)
    slot_rows = dict(
        db.query(models.AppOpen.meal_slot, func.count(models.AppOpen.id))
        .group_by(models.AppOpen.meal_slot)
        .all()
    )
    return {
        # Promedio de aperturas por (usuario, semana): la respuesta a la BQ
        "average_opens_per_user_per_week": round(total_opens / user_weeks, 2) if user_weeks else 0.0,
        "total_opens": total_opens,
        "active_users": len({row.user_id for row in per_user_week}),
        "user_weeks": user_weeks,
        "opens_by_meal_slot": [{"meal_slot": s, "count": slot_rows.get(s, 0)} for s in MEAL_SLOTS],
    }


@router.get("/app-opens/weekly", response_model=schemas.WeeklyOpensSummary)
def get_weekly_opens(db: Session = Depends(get_db)):
    return _weekly_opens_summary(db)


# Reporte CSV: una fila por usuario y semana (sin correos ni nombres, solo el id interno)
@router.get("/app-opens/export")
def export_app_opens(db: Session = Depends(get_db)):
    week = func.strftime("%Y-%W", models.AppOpen.timestamp)
    rows = (
        db.query(models.AppOpen.user_id, week.label("week"), func.count(models.AppOpen.id).label("opens"))
        .group_by(models.AppOpen.user_id, week)
        .order_by(week)
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "week", "opens"])
    for r in rows:
        writer.writerow([r.user_id, r.week, r.opens])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=app_opens_report.csv"},
    )
