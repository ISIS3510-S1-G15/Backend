# SYNTHETIC DEMO DATA for the BQ Type 2 dashboard (time to selection + Quick Pick). These rows are generated,
# not real usage: the wiki must say so. Runs on top of seed_demo_data.py, reusing its demo users, meal-slot
# weights and Colombia-time clock, and never touches other BQ tables.
import argparse
import sys
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.database import engine
from app.routers.place_selection import MIN_PERSONAL_PICKS
from scripts.import_sqlite import ImportFailure, require_schema
from scripts.seed_demo_data import DEMO_DOMAIN, DEMO_PREFIX, RESTAURANTS, SLOT_HOURS, SLOT_WEIGHTS, Builder

Event = models.PlaceSelectionEvent
DEMO_EMAILS = models.User.email.like(f"{DEMO_PREFIX}%{DEMO_DOMAIN}")
FAVORITE_RATE = 0.6
QUICK_PICK_RATE = 0.35
QUICK_PICK_DAYS = 14  # the shortcut only "exists" in the last two weeks, so before/after can be compared


def demo_users(session: Session) -> list[models.User]:
    return list(session.scalars(select(models.User).where(DEMO_EMAILS).order_by(models.User.id)))


def existing_demo_selections(session: Session) -> int:
    # Rows with a source were written by this script (or the Sprint 4 app), never by Sprint 3.
    return session.execute(
        select(func.count()).select_from(Event).join(models.User, models.User.id == Event.user_id)
        .where(DEMO_EMAILS, Event.source.is_not(None))
    ).scalar()


class SelectionBuilder:
    def __init__(self, seed: int, weeks: int):
        self.clock = Builder(seed, weeks)  # shared RNG, slot weights and Colombia-time moments
        self.rng = self.clock.rng
        self.weeks = weeks
        self.rows: list[Event] = []

    def detail_ms(self, pace: float) -> int:
        # Skewed: most users decide in 20-120 s, a tail browses for 3-10 min.
        seconds = self.rng.uniform(20, 120) if self.rng.random() < 0.8 else self.rng.uniform(180, 600)
        return int(seconds * pace * 1000)

    def build_user(self, user: models.User) -> None:
        favorites = {slot: self.rng.choice(RESTAURANTS) for slot in SLOT_WEIGHTS}
        pace = self.rng.uniform(0.6, 1.5)  # some students are slower deciders than others
        moments = []
        for week in range(self.weeks):
            for _ in range(self.rng.randint(3, 7)):
                slot = self.clock.slot()
                moments.append((self.clock.moment(7 * (week + 1), SLOT_HOURS[slot], 7 * week), slot))
        cutoff = self.clock.now - timedelta(days=QUICK_PICK_DAYS)
        picks: dict[tuple[str, str], int] = {}
        for stamp, slot in sorted(moments):
            favorite = favorites[slot]
            # Same rule as /me/quick-pick: the shortcut only exists once the favorite is a habit.
            has_habit = picks.get((slot, favorite), 0) >= MIN_PERSONAL_PICKS
            if stamp >= cutoff and has_habit and self.rng.random() < QUICK_PICK_RATE:
                restaurant, source, ms = favorite, "quick_pick", int(self.rng.uniform(5, 40) * 1000)
            else:
                restaurant = favorite if self.rng.random() < FAVORITE_RATE else self.rng.choice(RESTAURANTS)
                source, ms = "detail", self.detail_ms(pace)
            picks[(slot, restaurant)] = picks.get((slot, restaurant), 0) + 1
            self.rows.append(Event(
                user_id=user.id, restaurant_id=restaurant, ms_since_app_open=ms,
                meal_slot=slot, source=source, received_at=stamp.replace(tzinfo=None),
            ))


def run(seed: int, weeks: int, dry_run: bool) -> int:
    with engine.connect() as probe:
        require_schema(probe)
    with Session(engine) as session:
        users = demo_users(session)
        if not users:
            raise ImportFailure(
                "No hay usuarios de demostracion; ejecuta primero: python -m scripts.seed_demo_data"
            )
        if existing_demo_selections(session):
            raise ImportFailure(
                "Ya existen selecciones de demostracion con source; no se siembra nada"
            )
        builder = SelectionBuilder(seed, weeks)
        for user in users:
            builder.build_user(user)
        session.add_all(builder.rows)
        counts: dict[str, int] = {}
        for row in builder.rows:
            counts[row.__tablename__] = counts.get(row.__tablename__, 0) + 1
        if dry_run:
            session.rollback()
        else:
            session.commit()
    for table, total in sorted(counts.items()):
        print(f"{table:<24} {total}")
    print("SIMULACION (no se escribio nada)" if dry_run else "DATOS DE DEMOSTRACION CREADOS")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Siembra selecciones sinteticas para el dashboard de la BQ Type 2")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--weeks", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run(args.seed, args.weeks, args.dry_run)
    except ImportFailure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
