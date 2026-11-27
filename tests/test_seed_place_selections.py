from datetime import datetime, timedelta

from sqlalchemy import func

from app import models
from scripts import seed_demo_data, seed_place_selections

Event = models.PlaceSelectionEvent


def test_requires_demo_users(capsys, db):
    assert seed_place_selections.main([]) == 1
    assert "seed_demo_data" in capsys.readouterr().err
    assert db.query(func.count(Event.id)).scalar() == 0


def test_dry_run_writes_nothing(db):
    assert seed_demo_data.main([]) == 0
    assert seed_place_selections.main(["--dry-run"]) == 0
    assert db.query(func.count(Event.id)).scalar() == 0


def test_seeds_once_and_feeds_by_source(client, capsys, db):
    assert seed_demo_data.main([]) == 0
    assert seed_place_selections.main([]) == 0
    total = db.query(func.count(Event.id)).scalar()
    assert total > 100

    assert seed_place_selections.main([]) == 1
    assert "Ya existen selecciones de demostracion" in capsys.readouterr().err
    assert db.query(func.count(Event.id)).scalar() == total

    rows = {row["source"]: row for row in client.get("/analytics/time-to-selection/by-source").json()["by_source"]}
    assert rows["detail"]["selections"] > 0 and rows["quick_pick"]["selections"] > 0
    assert rows["quick_pick"]["avg_seconds"] < rows["detail"]["avg_seconds"]

    # The shortcut only shows up in the last two weeks.
    oldest_quick = db.query(func.min(Event.received_at)).filter(Event.source == "quick_pick").scalar()
    assert oldest_quick >= datetime.utcnow() - timedelta(days=15)
