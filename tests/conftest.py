import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

_base_url = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
if not _base_url.startswith(("postgresql://", "postgres://")):
    pytest.exit("Define DATABASE_URL (PostgreSQL) en .env antes de ejecutar los tests", returncode=2)

_parts = urlsplit(_base_url)
if _parts.hostname not in ("127.0.0.1", "localhost", "::1"):
    pytest.exit(
        "Los tests solo se ejecutan contra el PostgreSQL local (Docker). "
        "DATABASE_URL apunta a un servidor remoto; usa una base local para pytest.",
        returncode=2,
    )
_test_db = _parts.path.lstrip("/") + "_test"
_admin_url = urlunsplit(_parts._replace(path="/postgres"))
TEST_DATABASE_URL = urlunsplit(_parts._replace(path="/" + _test_db))

with psycopg.connect(_admin_url, autocommit=True, connect_timeout=10) as _admin:
    if not _admin.execute("select 1 from pg_database where datname = %s", (_test_db,)).fetchone():
        _admin.execute(f'create database "{_test_db}"')

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app import models
from app.database import Base, SessionLocal, engine
from app.main import app


def _alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


@pytest.fixture(scope="session", autouse=True)
def schema():
    assert engine.url.database.endswith("_test")
    command.upgrade(_alembic_config(), "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(schema):
    assert engine.url.database.endswith("_test")
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables if t.name not in ("restaurants", "catalog_options"))
    with engine.begin() as conn:
        conn.exec_driver_sql(f"truncate {names} restart identity cascade")
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_user(client):
    counter = {"n": 0}

    def _make(name="Tester"):
        counter["n"] += 1
        email = f"user{counter['n']}@uniandes.edu.co"
        response = client.post(
            "/auth/register", json={"name": name, "email": email, "password": "Password1!"}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        return {
            "id": body["user"]["id"],
            "email": email,
            "headers": {"Authorization": f"Bearer {body['access_token']}"},
        }

    return _make
