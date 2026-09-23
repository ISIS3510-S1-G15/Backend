from fastapi import FastAPI
from app.database import engine, Base
from app.routers import analytics
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)  # crea las tablas si no existen

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

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Campus Eats backend is running"}