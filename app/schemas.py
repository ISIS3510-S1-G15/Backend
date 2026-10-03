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

#cuando Flutter mande un evento del onboarding: la sesión, qué pasó y en qué paso
class OnboardingEventCreate(BaseModel):
    session_id: str
    event: str  # "started", "step" o "completed"
    step: int

class OnboardingEventOut(BaseModel):
    id: int
    session_id: str
    event: str
    step: int
    timestamp: datetime

    class Config:
        from_attributes = True

#cuántas sesiones llegaron hasta cada paso
class StepReach(BaseModel):
    step: int
    sessions: int

#Forma de respuesta del resumen
class OnboardingCompletionSummary(BaseModel):
    started: int            # sesiones que abrieron la encuesta
    completed: int          # sesiones que guardaron sus preferencias
    completion_rate: float  # porcentaje de sesiones completadas
    reached_by_step: list[StepReach]  # muestra en qué paso abandonan los usuarios


#cuando Flutter mande el uso de un filtro, espero el nombre del filtro y la pantalla
class FilterUsageCreate(BaseModel):
    filter: str
    screen: str

class FilterUsageOut(BaseModel):
    id: int
    filter: str
    screen: str
    timestamp: datetime

    class Config:
        from_attributes = True

#Forma de respuesta del resumen
class FilterUsageSummary(BaseModel):
    filter: str
    screen: str
    count: int  # cuántas veces se usó ese filtro en esa pantalla
