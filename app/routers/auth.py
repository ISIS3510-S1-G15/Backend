# Autenticación de usuarios (Juan Felipe Ochoa)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# La app es para la comunidad de la universidad, así que solo se aceptan correos institucionales
ALLOWED_DOMAIN = "@uniandes.edu.co"


def _token_response(user: models.User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user}


# Crea la cuenta y deja al usuario con la sesión iniciada (devuelve el token de una vez)
@router.post("/register", response_model=schemas.TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not email.endswith(ALLOWED_DOMAIN) or email.count("@") != 1 or email.startswith("@"):
        raise HTTPException(status_code=422, detail=f"Use your institutional email ({ALLOWED_DOMAIN})")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = models.User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email.strip().lower()).first()
    # Mismo mensaje si el correo no existe o si la contraseña es incorrecta: no revela qué correos están registrados
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _token_response(user)


# La app lo llama al arrancar para saber si el token guardado sigue siendo válido
@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
