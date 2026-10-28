from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import json
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID
from app import section_catalog

# ---------- BQ type 3: What categories of food or restaurants do users search for without getting any results? ----------
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


class OccupancyCheckCreate(BaseModel):
    restaurant_id: str = Field(min_length=1, max_length=100)
    screen: str = Field(min_length=1, max_length=50)
    action: Literal["checked", "selected"]


class OccupancyCheckOut(BaseModel):
    id: int
    restaurant_id: str
    screen: str
    action: str
    timestamp: datetime

    class Config:
        from_attributes = True


class OccupancyCheckSummary(BaseModel):
    restaurant_id: str
    checks: int
    selections: int
    selection_rate: float


class ProfileEditCreate(BaseModel):
    install_id: str = Field(min_length=1, max_length=100)
    field: Literal["dietary_restrictions", "cuisine_preferences"]


class ProfileEditOut(BaseModel):
    id: int
    install_id: str
    field: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ProfileEditSummary(BaseModel):
    install_id: str
    edits: int
    last_edit: datetime


class ProfileEditFieldSummary(BaseModel):
    field: str
    edits: int
    installs: int

# BQ Type 5 Tags counters: What are the main tags restaurants have when an user decides to visit it?
class TagClickCreate(BaseModel):
    # La app enviara la lista de tags (ej. ["Vegan", "Fast Food"])
    tags: list[str]

class TagClickOut(BaseModel):
    tag: str
    count: int

    class Config:
        from_attributes = True

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

# ---------- BQ type 2: How often do users check or inquire about a restaurant’s occupancy level before deciding to go? ----------
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

class OccupancyCheckRateSummary(BaseModel):
    checks: int                       # veces que se vio el indicador de ocupación
    checks_without_data: int          # de esas, cuántas no tenían reportes que mostrar
    go_decisions: int                 # veces que tocaron "Get directions"
    decisions_after_check: int        # decisiones con una revisión del mismo usuario y lugar en los 30 min previos
    check_before_go_rate: float       # decisions_after_check / go_decisions * 100 (respuesta de la BQ)
    avg_checks_per_user_per_week: float
    by_restaurant: list[OccupancyCheckByRestaurant]
    

# ---------- BQ Type 3: What places are saved as favorites but rarely viewed in detail again? ----------
class RestaurantViewCreate(BaseModel):
    restaurant_id: str

class RestaurantViewLogged(BaseModel):
    saved: bool

class SavedRarelyViewedPlace(BaseModel):
    restaurant_id: str
    times_saved: int              # cuántos usuarios lo tienen guardado
    rarely_viewed: int            # de esos, cuántos lo abrieron max_views veces o menos después de guardarlo
    rarely_viewed_pct: float      # rarely_viewed / times_saved * 100
    avg_views_after_saving: float

class SavedRarelyViewedSummary(BaseModel):
    max_views: int                # "rarely" = esta cantidad de vistas o menos después de guardar
    min_days_saved: int           # solo cuentan guardados con al menos estos días de antigüedad
    saves_analyzed: int
    rarely_viewed: int
    rarely_viewed_pct: float      # respuesta general de la BQ
    places: list[SavedRarelyViewedPlace]  # ordenados de más a menos "olvidados"
    
    
    
# ---------- APP ----------
# Restaurantes guardados 
class SavedRestaurantsOut(BaseModel):
    restaurant_ids: list[str]  # del más reciente al más antiguo
    
# ---------- Perfil de la encuesta de preferencias ----------
class ProfileData(BaseModel):
    name: str = Field(default="", max_length=60)
    cuisines: list[str] = []
    dietary_restrictions: list[str] = []
    meal_frequency: str = ""
    meal_times: list[str] = []
    budget: str = ""
    priorities: list[str] = Field(default=[], max_length=3) 
    disliked_foods: str = Field(default="", max_length=300)

class ProfileOut(ProfileData):
    completed: bool  # False si el usuario todavía no ha guardado la encuesta

    class Config:
        from_attributes = True


# ---------- Reseñas ----------
# Lo que manda la app al escribir una reseña. El autor NO viene aquí: sale del token
class ReviewCreate(BaseModel):
    taste: int = Field(ge=1, le=5)
    attention: int = Field(ge=1, le=5)
    price: int = Field(ge=1, le=5)
    options: int = Field(ge=1, le=5)
    dietary_options: list[str] = Field(default=[], max_length=10)
    comment: str = Field(default="", max_length=300)  # mismo límite que el contador 0/300 de la app

    # Quita espacios sobrantes para no guardar comentarios que son solo espacios
    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: str) -> str:
        return v.strip()


class ReviewOut(BaseModel):
    id: int
    restaurant_id: str
    author: str               # nombre de la cuenta de quien la escribió
    created_at: datetime      # con zona UTC, para que la app la convierta a hora local
    taste: int
    attention: int
    price: int
    options: int
    dietary_options: list[str]
    comment: str


# Rating de un restaurante: promedio del "overall" de cada reseña (promedio de sus 4 categorías)
class RatingSummary(BaseModel):
    restaurant_id: str
    rating: float | None      # None si todavía no tiene reseñas
    review_count: int


class RestaurantReviewsOut(RatingSummary):
    reviews: list[ReviewOut]  # más nuevas primero


# ---------- Reportes de ocupación ----------
class OccupancyReportCreate(BaseModel):
    restaurant_id: str = Field(min_length=1)
    level: int = Field(ge=0, le=2)  # 0 vacío, 1 moderado, 2 lleno


# Estado de ocupación de un restaurante en este momento
class OccupancyOut(BaseModel):
    restaurant_id: str
    level: float | None       # promedio 0-2 de los reportes recientes; None si no hay
    reports: list[int]        # niveles usados en el promedio (más nuevos primero)
    last_report_at: datetime | None


class SectionEventIn(BaseModel):
    event_id: UUID
    event_type: section_catalog.SectionEventType
    section: section_catalog.SectionName
    action: str | None = None
    visit_id: UUID
    client_timestamp: datetime
    extra: dict[str, str | int | float | bool] | None = None

    @field_validator("client_timestamp")
    @classmethod
    def timestamp_in_accepted_window(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if value > now + timedelta(minutes=section_catalog.MAX_FUTURE_SKEW_MINUTES):
            raise ValueError("client_timestamp is in the future")
        if value < now - timedelta(days=section_catalog.MAX_EVENT_AGE_DAYS):
            raise ValueError("client_timestamp is too old")
        return value

    @field_validator("extra")
    @classmethod
    def extra_is_small(cls, value):
        if value is None:
            return value
        if len(value) > section_catalog.MAX_EXTRA_KEYS:
            raise ValueError("extra has too many keys")
        if len(json.dumps(value)) > section_catalog.MAX_EXTRA_BYTES:
            raise ValueError("extra is too large")
        return value

    @model_validator(mode="after")
    def action_matches_section(self):
        if self.event_type == section_catalog.SECTION_VIEW:
            if self.action is not None:
                raise ValueError("section_view must not carry an action")
        elif self.action not in section_catalog.ALLOWED_ACTIONS[self.section]:
            raise ValueError("action is not valid for this section")
        return self


class SectionEventBatch(BaseModel):
    events: list[SectionEventIn] = Field(min_length=1, max_length=section_catalog.MAX_BATCH_SIZE)


class SectionEventsAccepted(BaseModel):
    accepted: int
    duplicates: int


class MenuItemOut(BaseModel):
    name: str
    price: str
    description: str


class MenuSectionOut(BaseModel):
    category: str
    items: list[MenuItemOut]


class RestaurantOut(BaseModel):
    id: str
    name: str
    location: str
    category: str
    image_key: str | None
    image_url: str | None
    rating: float
    review_count: int
    price: str
    wait_time: str
    tags: list[str]
    hours: str
    description: str
    map_x: float
    map_y: float
    latitude: float
    longitude: float
    menu: list[MenuSectionOut]

    model_config = {"from_attributes": True}


class RestaurantListOut(BaseModel):
    restaurants: list[RestaurantOut]


class CatalogOptionOut(BaseModel):
    value: str
    label: str
    detail: str | None
    emoji: str | None
    extra: dict[str, Any] | None

    model_config = {"from_attributes": True}


class CatalogOut(BaseModel):
    groups: dict[str, list[CatalogOptionOut]]
