from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=schemas.CatalogOut)
def get_catalog(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(models.CatalogOption).order_by(models.CatalogOption.group_key, models.CatalogOption.sort_order)
    ).all()
    groups: dict[str, list[models.CatalogOption]] = {}
    for row in rows:
        groups.setdefault(row.group_key, []).append(row)
    return {"groups": groups}
