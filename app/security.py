# Utilidades de seguridad para la autenticación (Juan Felipe Ochoa)
# - Las contraseñas se guardan como hash bcrypt (nunca en texto plano)
# - Al iniciar sesión se entrega un JWT firmado; la app lo manda en cada petición protegida
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import models
from app.database import get_db

load_dotenv()  # permite definir JWT_SECRET en un archivo .env (que NO se sube al repo)

# En producción JWT_SECRET debe venir de una variable de entorno; el valor por defecto es solo para desarrollo local
SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-change-me")
ALGORITHM = "HS256"
TOKEN_DAYS = 7  # el usuario no tiene que volver a iniciar sesión durante una semana

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


# Dependencia de FastAPI: cualquier endpoint que la use solo funciona con un token válido
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(models.User, user_id)
    if user is None:
        raise unauthorized
    return user
