from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

# TABLA QUE GUARDA RESULTADOS NO ENCONTRADOS PARA BQ TYPE 3
class ZeroResultSearch(Base):
    __tablename__ = "zero_result_searches"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)      # el término que el usuario buscó
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

# TABLA QUE GUARDA LOS EVENTOS DE LA ENCUESTA DE ONBOARDING PARA BQ TYPE 2
class OnboardingEvent(Base):
    __tablename__ = "onboarding_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)  # identifica un mismo recorrido de la encuesta
    event = Column(String, index=True)       # "started", "step" o "completed"
    step = Column(Integer)                   # paso alcanzado (1 a 5)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
