from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Index, Uuid, Float, Text, JSON
from sqlalchemy.sql import func
from app.database import Base

# ---------- Business Questions ----------

# BQ type 3: What categories of food or restaurants do users search for without getting any results?
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


# TABLA QUE GUARDA CADA USO DE UN FILTRO PARA BQ TYPE 2
class FilterUsage(Base):
    __tablename__ = "filter_usages"

    id = Column(Integer, primary_key=True, index=True)
    filter = Column(String, index=True)     # el filtro que el usuario tocó (ej. "open", "Vegan")
    screen = Column(String, index=True)     # la pantalla donde lo tocó (ej. "map", "home")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class OccupancyCheck(Base):
    __tablename__ = "occupancy_checks"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(String, index=True)
    screen = Column(String, index=True)
    action = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class ProfileEdit(Base):
    __tablename__ = "profile_edits"

    id = Column(Integer, primary_key=True, index=True)
    install_id = Column(String, index=True)
    field = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# ---------- Autenticación + BQ TYPE 1 (Juan Felipe Ochoa) ----------
from sqlalchemy import ForeignKey


# Usuarios registrados. La contraseña NUNCA se guarda en texto plano, solo su hash bcrypt
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Una fila cada vez que un usuario autenticado abre (o vuelve a) la app
# BQ Type 1: "On average, how many times does a user open the app during a typical academic week?"
class AppOpen(Base):
    __tablename__ = "app_opens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    meal_slot = Column(String)  # contexto de la apertura: Breakfast, Lunch, Dinner, ...
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
   
#BQ type 2: How often do users check or inquire about a restaurant’s occupancy level before deciding to go?
#Una fila cuando el usuario ve el indicador de ocupación de un restaurante ("occupancy_checked")
#o toca "Get directions" para ir ("go_decision")
class OccupancyEvent(Base):
    __tablename__ = "occupancy_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    restaurant_id = Column(String, index=True, nullable=False)
    event = Column(String, index=True, nullable=False)  #"occupancy_checked" o "go_decision"
    has_data = Column(Boolean, nullable=True)            #solo en "occupancy_checked": ¿había reportes que mostrar?
    timestamp = Column(DateTime, index=True, nullable=False) 
    

# BQ Type 3: What places are saved as favorites but rarely viewed in detail again?
# Una fila cada vez que un usuario abre el detalle de un restaurante
class RestaurantView(Base):
    __tablename__ = "restaurant_views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    restaurant_id = Column(String, index=True, nullable=False)
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

# BQ Type 5: What are the main tags restaurants have when an user decides to visit it?
# Una fila por tag y se aumenta su contador cada que un usuario decide ir a un restaurante 
class TagClickCounter(Base):
    __tablename__ = "tag_click_counters"

    tag = Column(String, primary_key=True, index=True)
    count = Column(Integer, default=1, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------- APP ----------
# Restaurantes que cada usuario guardó (botón del detalle). Una fila por par usuario-restaurante
class SavedRestaurant(Base):
    __tablename__ = "saved_restaurants"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    restaurant_id = Column(String, primary_key=True)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())
    
# Respuestas de la encuesta de preferencias de cada usuario (una fila por usuario).
from sqlalchemy import JSON

class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    name = Column(String, default="")
    cuisines = Column(JSON, default=list)
    dietary_restrictions = Column(JSON, default=list)
    meal_frequency = Column(String, default="")
    meal_times = Column(JSON, default=list)
    budget = Column(String, default="")
    priorities = Column(JSON, default=list)
    disliked_foods = Column(String, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ---------- Reseñas y ocupación (Juan Felipe Ochoa) ----------
# Antes vivían en la app: reseñas en reviews_data.dart (en memoria) y ocupación en SharedPreferences del celular.
# restaurant_id es texto y sin ForeignKey, igual que en SavedRestaurant, porque la tabla restaurants todavía no existe
from sqlalchemy import Text, UniqueConstraint


# Una reseña por usuario y restaurante: si el usuario vuelve a reseñar, se actualiza la suya
# (así una sola persona no puede subir o bajar el rating escribiendo muchas reseñas)
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "restaurant_id", name="uq_review_user_restaurant"),)

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    taste = Column(Integer, nullable=False)       # 1 a 5: Taste & Food Quality
    attention = Column(Integer, nullable=False)   # 1 a 5: Service & Attention
    price = Column(Integer, nullable=False)       # 1 a 5: Value for Money
    options = Column(Integer, nullable=False)     # 1 a 5: Dietary Options
    dietary_options = Column(JSON, default=list)  # dietas que el autor dice que el lugar ofrece
    comment = Column(Text, default="")
    # Hora UTC sin zona, puesta desde Python (igual que OccupancyEvent) para poder compararla sin errores
    created_at = Column(DateTime, index=True, nullable=False)


# Un reporte de "qué tan lleno está" (0 vacío, 1 moderado, 2 lleno). Se guardan todos (historial para BQs);
# al leer solo se usan los recientes y el último de cada usuario
class OccupancyReport(Base):
    __tablename__ = "occupancy_reports"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(String, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    level = Column(Integer, nullable=False)
    created_at = Column(DateTime, index=True, nullable=False)


class SectionEvent(Base):
    __tablename__ = "section_events"
    __table_args__ = (
        Index("ix_section_events_section_type_time", "section", "event_type", "client_timestamp"),
    )

    event_id = Column(Uuid, primary_key=True)
    event_type = Column(String(32), nullable=False)
    section = Column(String(32), nullable=False)
    action = Column(String(48))
    visit_id = Column(Uuid, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    client_timestamp = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    extra = Column(JSON)


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    category = Column(String, nullable=False)
    image_key = Column(String)
    image_url = Column(String)
    rating = Column(Float, nullable=False)
    review_count = Column(Integer, nullable=False)
    price = Column(String, nullable=False)
    wait_time = Column(String, nullable=False)
    tags = Column(JSON, nullable=False)
    hours = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    map_x = Column(Float, nullable=False)
    map_y = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    menu = Column(JSON, nullable=False)


class CatalogOption(Base):
    __tablename__ = "catalog_options"

    group_key = Column(String(48), primary_key=True)
    value = Column(String(64), primary_key=True)
    label = Column(String, nullable=False)
    detail = Column(String)
    emoji = Column(String(16))
    extra = Column(JSON)
    sort_order = Column(Integer, nullable=False)
