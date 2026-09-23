from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#usa un archivo llamado campus_eats.db como base de datos
SQLALCHEMY_DATABASE_URL = "sqlite:///./campus_eats.db"

#motor que sabe como lerr o escribir ese archivo .db
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Se usa en cada endpoint para obtener una sesión de base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()