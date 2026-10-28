from fastapi import FastAPI
from app.routers import analytics, auth, occupancy_checks, saved, profile, saved_views, reviews, occupancy, section_usage, restaurants, catalog
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Campus Eats API")
app.add_middleware(
    CORSMiddleware,
    # acepta peticiones desde cualquier origen
    allow_origins=["*"],
    # acepta cualquier tipo de petición (GET, POST, PUT, DELETE, etc.)
    allow_methods=["*"],
    # acepta cualquier encabezado que Flutter le mande (como Content-Type: application/json, que usamos para mandar el JSON)
    allow_headers=["*"],
)

app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(occupancy_checks.router)
app.include_router(saved.router)
app.include_router(profile.router)
app.include_router(saved_views.router)
app.include_router(reviews.router)
app.include_router(occupancy.router)
app.include_router(section_usage.router)
app.include_router(restaurants.router)
app.include_router(catalog.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Campus Eats backend is running"}