import sqlite3

import pytest
from sqlalchemy import func, select

from app import models
from app.database import SessionLocal, engine
from scripts.import_sqlite import main

SCHEMA = """
create table users (id integer primary key, email varchar not null, name varchar not null,
    password_hash varchar not null, created_at datetime default current_timestamp);
create table app_opens (id integer primary key, user_id integer not null references users(id),
    meal_slot varchar, timestamp datetime default current_timestamp);
create table occupancy_events (id integer primary key, user_id integer not null references users(id),
    restaurant_id varchar not null, event varchar not null, has_data boolean, timestamp datetime not null);
create table user_profiles (user_id integer primary key references users(id), name varchar,
    cuisines json, dietary_restrictions json, meal_frequency varchar, meal_times json, budget varchar,
    priorities json, disliked_foods varchar, updated_at datetime);
"""


@pytest.fixture
def sqlite_file(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("insert into users values (7, 'x@uniandes.edu.co', 'Ñandú', '$2b$12$abcdefghijklmnopqrstuv', '2026-10-03 05:21:56')")
    conn.execute("insert into users values (9, 'y@uniandes.edu.co', 'Yo', '$2b$12$zyxwvutsrqponmlkjihgfe', '2026-10-04 10:00:00.250000')")
    conn.execute("insert into app_opens values (1, 7, 'Lunch', '2026-10-03 05:22:20')")
    conn.execute("insert into occupancy_events values (1, 7, 'r1', 'occupancy_checked', 1, '2026-10-03 06:00:00')")
    conn.execute("insert into occupancy_events values (2, 7, 'r1', 'go_decision', null, '2026-10-03 06:10:00')")
    conn.execute("insert into user_profiles values (7, 'Ñandú', '[\"Mexican\"]', '[]', 'daily', '[\"Lunch\"]', 'Low', '[\"Price\"]', '', '2026-10-05 00:00:00')")
    conn.commit()
    conn.close()
    return path


def test_import_preserves_data_and_blocks_second_run(sqlite_file, capsys):
    assert main([str(sqlite_file)]) == 0
    assert "IMPORTACION OK" in capsys.readouterr().out

    with SessionLocal() as db:
        users = {u.id: u for u in db.query(models.User).all()}
        assert set(users) == {7, 9}
        assert users[7].name == "Ñandú"
        assert users[7].password_hash == "$2b$12$abcdefghijklmnopqrstuv"
        assert users[7].created_at.isoformat() == "2026-10-03T05:21:56+00:00"
        assert users[9].created_at.microsecond == 250000
        events = {e.id: e for e in db.query(models.OccupancyEvent).all()}
        assert events[1].has_data is True and events[2].has_data is None
        assert events[1].timestamp.tzinfo is None
        assert db.get(models.UserProfile, 7).cuisines == ["Mexican"]

    assert main([str(sqlite_file)]) == 1
    assert "ya contiene datos" in capsys.readouterr().err
    with SessionLocal() as db:
        assert db.query(func.count(models.User.id)).scalar() == 2


def test_sequences_continue_after_import(sqlite_file):
    assert main([str(sqlite_file)]) == 0
    with SessionLocal() as db:
        user = models.User(email="new@uniandes.edu.co", name="New", password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id == 10
        opened = models.AppOpen(user_id=7, meal_slot="Dinner")
        db.add(opened)
        db.commit()
        db.refresh(opened)
        assert opened.id == 2


def test_verify_mode_does_not_write(sqlite_file, capsys):
    assert main([str(sqlite_file), "--verify"]) == 1
    capsys.readouterr()
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(models.User)).scalar() == 0
    assert main([str(sqlite_file)]) == 0
    assert main([str(sqlite_file), "--verify"]) == 0


def test_unknown_columns_abort_without_writing(tmp_path, capsys):
    path = tmp_path / "bad.db"
    conn = sqlite3.connect(path)
    conn.execute("create table users (id integer primary key, email varchar, name varchar, password_hash varchar, extra varchar)")
    conn.execute("insert into users values (1, 'a@uniandes.edu.co', 'A', 'h', 'z')")
    conn.commit()
    conn.close()
    assert main([str(path)]) == 1
    assert "columnas desconocidas" in capsys.readouterr().err
    with SessionLocal() as db:
        assert db.query(func.count(models.User.id)).scalar() == 0


def test_missing_file_is_reported(tmp_path, capsys):
    assert main([str(tmp_path / "nope.db")]) == 2
    assert "no existe" in capsys.readouterr().err
