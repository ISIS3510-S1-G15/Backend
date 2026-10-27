# Reseñas de los restaurantes (Juan Felipe Ochoa)
# Antes: reviews_data.dart en la app (en memoria, se perdían al cerrarla) y rating/reviews fijos en cada restaurante.
# Ahora: cada reseña se guarda con el usuario del token, y el rating y el número de reseñas se CALCULAN con esta tabla
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(tags=["reviews"])

# "Overall" de una reseña = promedio de sus 4 categorías (la misma fórmula que ReviewRatings.overall en la app)
_OVERALL = (models.Review.taste + models.Review.attention + models.Review.price + models.Review.options) / 4.0


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # UTC sin zona, como se guarda en SQLite


def _as_utc(dt: datetime) -> datetime:
    # SQLite devuelve la fecha sin zona. Se le marca UTC para que el JSON lleve "+00:00"
    # y Flutter la pueda pasar a hora de Colombia con toLocal()
    return dt.replace(tzinfo=timezone.utc)


def rating_summaries(db: Session, restaurant_ids: list[str] | None = None) -> dict[str, dict]:
    """Rating y número de reseñas por restaurante, en UNA sola consulta (GROUP BY).
    Pensado para que GET /restaurants lo reutilice cuando exista el catálogo en el backend."""
    query = db.query(
        models.Review.restaurant_id, func.avg(_OVERALL), func.count(models.Review.id)
    ).group_by(models.Review.restaurant_id)
    if restaurant_ids is not None:
        query = query.filter(models.Review.restaurant_id.in_(restaurant_ids))
    return {
        rid: {"restaurant_id": rid, "rating": round(avg, 1), "review_count": count}
        for rid, avg, count in query.all()
    }


def _summary_for(db: Session, restaurant_id: str) -> dict:
    empty = {"restaurant_id": restaurant_id, "rating": None, "review_count": 0}
    return rating_summaries(db, [restaurant_id]).get(restaurant_id, empty)


def _review_out(review: models.Review, author: str) -> dict:
    return {
        "id": review.id,
        "restaurant_id": review.restaurant_id,
        "author": author,
        "created_at": _as_utc(review.created_at),
        "taste": review.taste,
        "attention": review.attention,
        "price": review.price,
        "options": review.options,
        "dietary_options": review.dietary_options or [],
        "comment": review.comment or "",
    }


# Rating y número de reseñas de TODOS los restaurantes que tienen reseñas (para Home, Mapa, Search, Saved y Detalle)
@router.get("/reviews/summary", response_model=list[schemas.RatingSummary])
def get_rating_summaries(db: Session = Depends(get_db)):
    return list(rating_summaries(db).values())


# Reseñas de un restaurante (más nuevas primero) + su rating y número de reseñas
@router.get("/restaurants/{restaurant_id}/reviews", response_model=schemas.RestaurantReviewsOut)
def get_reviews(
    restaurant_id: str,
    limit: int = Query(default=50, ge=1, le=100),  # evita mandar miles de reseñas al celular de una vez
    db: Session = Depends(get_db),
):
    rows = (
        db.query(models.Review, models.User.name)
        .join(models.User, models.User.id == models.Review.user_id)  # el nombre del autor sale de su cuenta
        .filter(models.Review.restaurant_id == restaurant_id)
        .order_by(models.Review.created_at.desc(), models.Review.id.desc())
        .limit(limit)
        .all()
    )
    return {**_summary_for(db, restaurant_id), "reviews": [_review_out(r, name) for r, name in rows]}


# Crea la reseña del usuario del token para este restaurante; si ya tenía una, la reemplaza
@router.post("/restaurants/{restaurant_id}/reviews", response_model=schemas.ReviewOut)
def create_review(
    restaurant_id: str,
    payload: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    review = (
        db.query(models.Review)
        .filter(models.Review.user_id == current_user.id, models.Review.restaurant_id == restaurant_id)
        .first()
    )
    if review is None:
        review = models.Review(user_id=current_user.id, restaurant_id=restaurant_id)
        db.add(review)
    for field, value in payload.model_dump().items():
        setattr(review, field, value)
    review.created_at = _now()  # una reseña editada vuelve a quedar de primera
    db.commit()
    db.refresh(review)
    return _review_out(review, current_user.name)
