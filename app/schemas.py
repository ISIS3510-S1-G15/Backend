from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator 
import re
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

    # Mínimo una letra, un número y un carácter especial (cualquier cosa que no sea letra, número o espacio)
    @field_validator("password")
    @classmethod
    def password_fuerte(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v) or not re.search(r"[^A-Za-z0-9\s]", v):
            raise ValueError("La contraseña necesita al menos una letra, un número y un carácter especial")
        return v

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

# ---------- BQ type 2: ¿qué tan seguido revisan la ocupación antes de decidir ir? ----------
class OccupancyEventCreate(BaseModel):
    restaurant_id: str
    event: Literal["occupancy_checked", "go_decision"]
    has_data: bool | None = None  # solo para "occupancy_checked"

class OccupancyEventLogged(BaseModel):
    saved: bool

class OccupancyCheckByRestaurant(BaseModel):
    restaurant_id: str
    checks: int
    go_decisions: int
    decisions_after_check: int

class OccupancyCheckSummary(BaseModel):
    checks: int                       # veces que se vio el indicador de ocupación
    checks_without_data: int          # de esas, cuántas no tenían reportes que mostrar
    go_decisions: int                 # veces que tocaron "Get directions"
    decisions_after_check: int        # decisiones con una revisión del mismo usuario y lugar en los 30 min previos
    check_before_go_rate: float       # decisions_after_check / go_decisions * 100 (respuesta de la BQ)
    avg_checks_per_user_per_week: float
    by_restaurant: list[OccupancyCheckByRestaurant]
