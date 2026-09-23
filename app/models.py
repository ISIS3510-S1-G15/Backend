from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base

# TABLA QUE GUARDA RESULTADOS NO ENCONTRADOS PARA BQ TYPE 3
class ZeroResultSearch(Base):
    __tablename__ = "zero_result_searches"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)      # el término que el usuario buscó
    timestamp = Column(DateTime(timezone=True), server_default=func.now())