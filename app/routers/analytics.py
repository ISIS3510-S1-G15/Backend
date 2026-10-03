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

    
# http://127.0.0.1:8000/docs#/analytics/get_search_gaps_analytics_search_gaps_get
# http://127.0.0.1:8000/docs