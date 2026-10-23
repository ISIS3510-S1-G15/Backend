# Perfil de la encuesta de preferencias del usuario con sesión (antes solo vivía en memoria en la app)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/me/profile", tags=["profile"])

_FIELDS = list(schemas.ProfileData.model_fields)


def _out(profile: models.UserProfile | None) -> dict:
    if profile is None:
        return {**schemas.ProfileData().model_dump(), "completed": False}
    return {**{f: getattr(profile, f) for f in _FIELDS}, "completed": True}


# Perfil guardado del usuario (vacío y completed=false si nunca hizo la encuesta)
@router.get("", response_model=schemas.ProfileOut)
def get_profile(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _out(db.get(models.UserProfile, current_user.id))


# Guarda las respuestas de la encuesta (la primera vez y cada vez que la vuelve a hacer)
@router.put("", response_model=schemas.ProfileOut)
def save_profile(
    payload: schemas.ProfileData,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    profile = db.get(models.UserProfile, current_user.id)
    if profile is None:
        profile = models.UserProfile(user_id=current_user.id)
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return _out(profile)
