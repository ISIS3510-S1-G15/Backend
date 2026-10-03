from typing import Literal
from pydantic import BaseModel, Field
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


# ---------- Autenticación (Juan Felipe Ochoa) ----------
class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=72)  # bcrypt solo usa los primeros 72 bytes

class LoginRequest(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True

# Lo que recibe la app al registrarse o iniciar sesión: el token y quién es el usuario
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- BQ TYPE 1: aperturas de la app (Juan Felipe Ochoa) ----------
# Las mismas franjas que usa la encuesta de preferencias ("When do you eat on campus?")
MealSlot = Literal["Breakfast", "Mid-morning snack", "Lunch", "Afternoon snack", "Dinner", "Late night"]

class AppOpenCreate(BaseModel):
    meal_slot: MealSlot

class AppOpenLogged(BaseModel):
    saved: bool

class MealSlotCount(BaseModel):
    meal_slot: str
    count: int

# Respuesta de la BQ
class WeeklyOpensSummary(BaseModel):
    average_opens_per_user_per_week: float  # la respuesta a la BQ
    total_opens: int
    active_users: int
    user_weeks: int  # pares (usuario, semana) con al menos una apertura
    opens_by_meal_slot: list[MealSlotCount]  # en qué momento del día abren la app
