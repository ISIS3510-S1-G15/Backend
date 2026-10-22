# Restaurantes guardados por el usuario con sesión (antes era el campo fijo "saved" en restaurants_data.dart)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/me/saved", tags=["saved"])


def _saved_ids(db: Session, user_id: int) -> list[str]:
    rows = (
        db.query(models.SavedRestaurant.restaurant_id)
        .filter(models.SavedRestaurant.user_id == user_id)
        .order_by(models.SavedRestaurant.saved_at.desc())
        .all()
    )
    return [r.restaurant_id for r in rows]


# Lista de ids guardados por el usuario
@router.get("", response_model=schemas.SavedRestaurantsOut)
def get_saved(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return {"restaurant_ids": _saved_ids(db, current_user.id)}


# Guarda un restaurante (si ya estaba guardado no pasa nada)
@router.put("/{restaurant_id}", response_model=schemas.SavedRestaurantsOut)
def save_restaurant(
    restaurant_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    if db.get(models.SavedRestaurant, (current_user.id, restaurant_id)) is None:
        db.add(models.SavedRestaurant(user_id=current_user.id, restaurant_id=restaurant_id))
        db.commit()
    return {"restaurant_ids": _saved_ids(db, current_user.id)}


# Quita un restaurante de guardados (si no estaba guardado no pasa nada)
@router.delete("/{restaurant_id}", response_model=schemas.SavedRestaurantsOut)
def unsave_restaurant(
    restaurant_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    entry = db.get(models.SavedRestaurant, (current_user.id, restaurant_id))
    if entry is not None:
        db.delete(entry)
        db.commit()
    return {"restaurant_ids": _saved_ids(db, current_user.id)}
