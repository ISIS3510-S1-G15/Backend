from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/restaurants", tags=["restaurants"])


@router.get("", response_model=schemas.RestaurantListOut)
def list_restaurants(db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Restaurant).order_by(models.Restaurant.id)).all()
    return {"restaurants": rows}


@router.get("/{restaurant_id}", response_model=schemas.RestaurantOut)
def get_restaurant(restaurant_id: str, db: Session = Depends(get_db)):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(404, "Restaurant not found")
    return restaurant
