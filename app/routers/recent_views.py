from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/me/recent-views", tags=["recent-views"])


def _recent_views(db: Session, user_id: int, limit: int) -> dict:
    view = models.RestaurantView
    last_viewed = func.max(view.viewed_at)
    rows = db.execute(
        select(view.restaurant_id, func.count().label("view_count"), last_viewed.label("last_viewed_at"))
        .where(view.user_id == user_id, view.hidden_at.is_(None))
        .group_by(view.restaurant_id)
        .order_by(last_viewed.desc(), view.restaurant_id)
        .limit(limit)
    ).all()
    return {
        "items": [
            {"restaurant_id": r.restaurant_id, "view_count": r.view_count, "last_viewed_at": r.last_viewed_at}
            for r in rows
        ]
    }


def _hide(db: Session, user_id: int, restaurant_id: str | None = None) -> None:
    view = models.RestaurantView
    statement = update(view).where(view.user_id == user_id, view.hidden_at.is_(None))
    if restaurant_id is not None:
        statement = statement.where(view.restaurant_id == restaurant_id)
    db.execute(statement.values(hidden_at=datetime.now(timezone.utc)))
    db.commit()


@router.get("", response_model=schemas.RecentViewsOut)
def get_recent_views(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _recent_views(db, current_user.id, limit)


@router.delete("/{restaurant_id}", response_model=schemas.RecentViewsOut)
def remove_recent_view(
    restaurant_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _hide(db, current_user.id, restaurant_id)
    return _recent_views(db, current_user.id, 30)


@router.delete("", response_model=schemas.RecentViewsOut)
def clear_recent_views(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _hide(db, current_user.id)
    return _recent_views(db, current_user.id, 30)
