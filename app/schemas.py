from pydantic import BaseModel
from datetime import datetime

#cuando Flutter mande una búsqueda nueva, solo espero que mande un texto llamado query
class ZeroResultSearchCreate(BaseModel):
    query: str  # lo único que Flutter necesita enviar

class ZeroResultSearchOut(BaseModel):
    id: int
    query: str
    timestamp: datetime

    class Config:
        from_attributes = True  # permite convertir el modelo de SQLAlchemy directamente

#Forma de respuesta
class SearchGapSummary(BaseModel):
    query: str
    count: int  # cuántas veces se buscó ese término sin resultados