import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()


def resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL no esta definida. Copia .env.example a .env y define DATABASE_URL "
            "(ej. postgresql://usuario:clave@localhost:5432/campus_eats)."
        )
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "DATABASE_URL debe ser una URL de PostgreSQL (postgresql://...). "
            "SQLite ya no esta soportado."
        )
    return url


SQLALCHEMY_DATABASE_URL = resolve_database_url()

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)


@event.listens_for(engine, "connect")
def _set_utc(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET TIME ZONE 'UTC'")
    cursor.close()
    dbapi_connection.commit()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
