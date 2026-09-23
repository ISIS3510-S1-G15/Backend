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

    
# http://127.0.0.1:8000/docs#/analytics/get_search_gaps_analytics_search_gaps_get
# http://127.0.0.1:8000/docs