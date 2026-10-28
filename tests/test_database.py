import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import models
from app.database import Base, engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_database(url):
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-c", "import app.database"], cwd=ROOT, env=env, capture_output=True, text=True
    )


def test_connects_to_postgresql():
    with engine.connect() as conn:
        assert conn.execute(text("select 1")).scalar() == 1
        assert "PostgreSQL" in conn.execute(text("select version()")).scalar()
        assert conn.execute(text("show timezone")).scalar().upper() == "UTC"


def test_migration_creates_every_table():
    names = set(inspect(engine).get_table_names())
    assert names == {t.name for t in Base.metadata.tables.values()} | {"alembic_version"}


def test_missing_database_url_fails_clearly():
    result = _import_database("")
    assert result.returncode != 0
    assert "DATABASE_URL no esta definida" in result.stderr


def test_sqlite_url_is_rejected():
    result = _import_database("sqlite:///./campus_eats.db")
    assert result.returncode != 0
    assert "SQLite ya no esta soportado" in result.stderr


def test_unique_email(db):
    db.add(models.User(email="a@uniandes.edu.co", name="A", password_hash="x"))
    db.commit()
    db.add(models.User(email="a@uniandes.edu.co", name="B", password_hash="y"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_foreign_key_is_enforced(db):
    db.add(models.AppOpen(user_id=9999, meal_slot="Lunch"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_not_null_is_enforced(db):
    db.add(models.User(email=None, name="A", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_rollback_discards_changes(db):
    db.add(models.User(email="rb@uniandes.edu.co", name="RB", password_hash="x"))
    db.flush()
    db.rollback()
    assert db.query(models.User).count() == 0


def test_autoincrement_and_timestamptz_default(db):
    first = models.User(email="s1@uniandes.edu.co", name="S1", password_hash="x")
    second = models.User(email="s2@uniandes.edu.co", name="S2", password_hash="x")
    db.add_all([first, second])
    db.commit()
    db.refresh(second)
    assert second.id == first.id + 1
    assert second.created_at.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - second.created_at).total_seconds()) < 60
