import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, section_catalog
from app.database import engine
from app.security import hash_password
from scripts.import_sqlite import ImportFailure, require_schema

DEMO_PASSWORD = "Demo1234!"
DEMO_DOMAIN = "@uniandes.edu.co"
DEMO_PREFIX = "demo"
RESTAURANTS = ["1", "2", "3", "4"]
COLOMBIA_UTC_OFFSET = 5

DEMO_NAMES = [
    "Valentina Rojas", "Santiago Mejia", "Camila Torres", "Mateo Herrera",
    "Isabella Garcia", "Samuel Castro", "Mariana Ortiz", "Daniel Vargas",
    "Sara Jimenez", "Nicolas Pardo", "Laura Beltran", "Andres Quintero",
]

SLOT_HOURS = {
    "Breakfast": (5, 8),
    "Mid-morning snack": (9, 10),
    "Lunch": (11, 13),
    "Afternoon snack": (14, 16),
    "Dinner": (17, 20),
    "Late night": (21, 23),
}
SLOT_WEIGHTS = {
    "Breakfast": 14,
    "Mid-morning snack": 12,
    "Lunch": 34,
    "Afternoon snack": 14,
    "Dinner": 20,
    "Late night": 6,
}

FILTER_PLAN = {
    "home": [("All", 18), ("Dining Hall", 22), ("Café", 30), ("Asian", 14), ("Burgers", 12), ("Indian", 8), ("Smoothies", 11)],
    "search": [("Vegan options", 34), ("Open late", 26), ("Open", 21), ("Quick pickup", 15), ("Coffee", 12), ("Halal", 9), ("Closed", 3)],
    "map": [("Open Now", 28), ("All Spots", 10), ("Dining Hall", 9), ("Café", 8)],
}

ZERO_RESULT_PLAN = [
    ("mexican", 14), ("tacos", 12), ("pizza", 11), ("breakfast", 9), ("arepas", 8),
    ("ramen", 7), ("empanadas", 6), ("vegan sushi", 5), ("postres", 4), ("gluten free", 4),
]

SECTION_PLAN = {
    "map": {"visits": 120, "engaged": 90},
    "filters": {"visits": 80, "engaged": 14},
    "details": {"visits": 100, "engaged": 72},
    "favorites": {"visits": 40, "engaged": 30},
}

VIEWS_AFTER_SAVING = {"1": (3, 8), "2": (1, 4), "3": (0, 1), "4": (0, 1)}


class Builder:
    def __init__(self, seed: int, weeks: int):
        self.rng = random.Random(seed)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.weeks = weeks
        self.rows: list = []
        self.users: list[models.User] = []

    def uuid(self) -> uuid.UUID:
        return uuid.UUID(int=self.rng.getrandbits(128), version=4)

    def moment(self, days_back: float, hour_range: tuple[int, int] | None = None, days_min: float = 0) -> datetime:
        day = self.now - timedelta(days=self.rng.uniform(days_min, days_back))
        for _ in range(20):
            if day.weekday() < 5 or self.rng.random() >= 0.7:
                break
            day = self.now - timedelta(days=self.rng.uniform(days_min, days_back))
        local_hour = self.rng.randint(*(hour_range or (7, 21)))
        result = day.replace(
            hour=(local_hour + COLOMBIA_UTC_OFFSET) % 24,
            minute=self.rng.randint(0, 59),
            second=self.rng.randint(0, 59),
        )
        if local_hour + COLOMBIA_UTC_OFFSET >= 24:
            result += timedelta(days=1)
        while result > self.now:
            result -= timedelta(days=1)
        return result

    def slot(self) -> str:
        return self.rng.choices(list(SLOT_WEIGHTS), weights=list(SLOT_WEIGHTS.values()))[0]

    def build_users(self) -> None:
        password_hash = hash_password(DEMO_PASSWORD)
        created = self.now - timedelta(weeks=self.weeks + 1)
        for index, name in enumerate(DEMO_NAMES, start=1):
            self.users.append(models.User(
                email=f"{DEMO_PREFIX}{index:02d}{DEMO_DOMAIN}",
                name=name,
                password_hash=password_hash,
                created_at=created + timedelta(days=index),
            ))

    def build_app_opens(self) -> None:
        for index, user in enumerate(self.users):
            heavy = index % 3 == 0
            for week in range(self.weeks):
                if self.rng.random() < 0.12:
                    continue
                opens = self.rng.randint(5, 9) if heavy else self.rng.randint(1, 5)
                for _ in range(opens):
                    slot = self.slot()
                    stamp = self.moment(7 * (week + 1), SLOT_HOURS[slot], 7 * week)
                    self.rows.append(models.AppOpen(user_id=user.id, meal_slot=slot, timestamp=stamp))

    def build_occupancy_events(self) -> None:
        for user in self.users:
            for _ in range(self.rng.randint(6, 12)):
                restaurant = self.rng.choice(RESTAURANTS)
                checked_at = self.moment(7 * self.weeks, (11, 14))
                has_data = self.rng.random() < 0.78
                self.rows.append(models.OccupancyEvent(
                    user_id=user.id, restaurant_id=restaurant, event="occupancy_checked",
                    has_data=has_data, timestamp=checked_at.replace(tzinfo=None),
                ))
                roll = self.rng.random()
                if roll < 0.62:
                    decided = checked_at + timedelta(minutes=self.rng.randint(1, 25))
                    self.rows.append(models.OccupancyEvent(
                        user_id=user.id, restaurant_id=restaurant, event="go_decision",
                        has_data=None, timestamp=min(decided, self.now).replace(tzinfo=None),
                    ))
                elif roll < 0.80:
                    decided = checked_at + timedelta(minutes=self.rng.randint(45, 240))
                    self.rows.append(models.OccupancyEvent(
                        user_id=user.id, restaurant_id=restaurant, event="go_decision",
                        has_data=None, timestamp=min(decided, self.now).replace(tzinfo=None),
                    ))
            for _ in range(self.rng.randint(0, 2)):
                self.rows.append(models.OccupancyEvent(
                    user_id=user.id, restaurant_id=self.rng.choice(RESTAURANTS), event="go_decision",
                    has_data=None, timestamp=self.moment(7 * self.weeks, (11, 14)).replace(tzinfo=None),
                ))

    def build_occupancy_checks(self) -> None:
        for restaurant in RESTAURANTS:
            checked = self.rng.randint(25, 60)
            selected = int(checked * self.rng.uniform(0.35, 0.5))
            for action, total in (("checked", checked), ("selected", selected)):
                for _ in range(total):
                    self.rows.append(models.OccupancyCheck(
                        restaurant_id=restaurant,
                        screen=self.rng.choice(["home", "map", "saved"]),
                        action=action,
                        timestamp=self.moment(7 * self.weeks),
                    ))

    def build_filter_usages(self) -> None:
        for screen, plan in FILTER_PLAN.items():
            for name, weight in plan:
                for _ in range(weight):
                    self.rows.append(models.FilterUsage(
                        filter=name, screen=screen, timestamp=self.moment(7 * self.weeks),
                    ))

    def build_onboarding(self) -> None:
        pass_rates = {2: 0.96, 3: 0.93, 4: 0.90, 5: 0.88}
        for number in range(1, 41):
            session = f"{DEMO_PREFIX}-ob-{number:03d}"
            stamp = self.moment(7 * self.weeks, (8, 20))
            self.rows.append(models.OnboardingEvent(session_id=session, event="started", step=1, timestamp=stamp))
            reached = 1
            for step in (2, 3, 4, 5):
                if self.rng.random() > pass_rates[step]:
                    break
                stamp += timedelta(seconds=self.rng.randint(15, 70))
                self.rows.append(models.OnboardingEvent(session_id=session, event="step", step=step, timestamp=stamp))
                reached = step
            if reached == 5 and self.rng.random() < 0.97:
                stamp += timedelta(seconds=self.rng.randint(10, 40))
                self.rows.append(models.OnboardingEvent(session_id=session, event="completed", step=5, timestamp=stamp))

    def build_profile_edits(self) -> None:
        for number in range(1, 9):
            install = f"{DEMO_PREFIX}-install-{number:02d}"
            for _ in range(self.rng.randint(1, 6)):
                field = self.rng.choices(
                    ["dietary_restrictions", "cuisine_preferences"], weights=[55, 45]
                )[0]
                self.rows.append(models.ProfileEdit(
                    install_id=install, field=field, timestamp=self.moment(7 * self.weeks),
                ))

    def build_zero_results(self) -> None:
        for term, weight in ZERO_RESULT_PLAN:
            for _ in range(weight):
                self.rows.append(models.ZeroResultSearch(query=term, timestamp=self.moment(7 * self.weeks)))

    def build_saves_and_views(self) -> None:
        for user in self.users:
            chosen = self.rng.sample(RESTAURANTS, self.rng.choice([2, 3]))
            for restaurant in chosen:
                saved_at = self.moment(25, (8, 20))
                saved_at = min(saved_at, self.now - timedelta(days=3))
                self.rows.append(models.SavedRestaurant(
                    user_id=user.id, restaurant_id=restaurant, saved_at=saved_at,
                ))
                low, high = VIEWS_AFTER_SAVING[restaurant]
                for _ in range(self.rng.randint(low, high)):
                    span = (self.now - saved_at).total_seconds() - 3600
                    viewed = saved_at + timedelta(seconds=3600 + self.rng.uniform(0, max(span, 1)))
                    self.rows.append(models.RestaurantView(user_id=user.id, restaurant_id=restaurant, viewed_at=viewed))
                if self.rng.random() < 0.5:
                    before = saved_at - timedelta(hours=self.rng.randint(2, 72))
                    self.rows.append(models.RestaurantView(user_id=user.id, restaurant_id=restaurant, viewed_at=before))
            for _ in range(self.rng.randint(0, 3)):
                other = self.rng.choice([r for r in RESTAURANTS if r not in chosen] or RESTAURANTS)
                self.rows.append(models.RestaurantView(
                    user_id=user.id, restaurant_id=other, viewed_at=self.moment(20),
                ))

    def build_section_events(self) -> None:
        for section, plan in SECTION_PLAN.items():
            actions = sorted(section_catalog.ALLOWED_ACTIONS[section])
            engaged_visits = set(self.rng.sample(range(plan["visits"]), plan["engaged"]))
            for number in range(plan["visits"]):
                user = self.rng.choice(self.users)
                visit = self.uuid()
                stamp = self.moment(6.5)
                self.rows.append(models.SectionEvent(
                    event_id=self.uuid(), event_type=section_catalog.SECTION_VIEW, section=section,
                    action=None, visit_id=visit, user_id=user.id, client_timestamp=stamp,
                ))
                if number in engaged_visits:
                    for _ in range(self.rng.randint(1, 3)):
                        stamp += timedelta(seconds=self.rng.randint(2, 40))
                        self.rows.append(models.SectionEvent(
                            event_id=self.uuid(), event_type=section_catalog.SECTION_INTERACTION,
                            section=section, action=self.rng.choice(actions), visit_id=visit,
                            user_id=user.id, client_timestamp=min(stamp, self.now),
                        ))

    def build_all(self) -> None:
        self.build_app_opens()
        self.build_occupancy_events()
        self.build_occupancy_checks()
        self.build_filter_usages()
        self.build_onboarding()
        self.build_profile_edits()
        self.build_zero_results()
        self.build_saves_and_views()
        self.build_section_events()


def existing_demo_users(session: Session) -> int:
    return session.execute(
        select(func.count()).select_from(models.User).where(
            models.User.email.like(f"{DEMO_PREFIX}%{DEMO_DOMAIN}")
        )
    ).scalar()


def run(seed: int, weeks: int, dry_run: bool) -> int:
    with engine.connect() as probe:
        require_schema(probe)
    with Session(engine) as session:
        if existing_demo_users(session):
            raise ImportFailure(
                "Ya existen usuarios de demostracion (demo##@uniandes.edu.co); no se siembra nada"
            )
        builder = Builder(seed, weeks)
        builder.build_users()
        session.add_all(builder.users)
        session.flush()
        builder.build_all()
        session.add_all(builder.rows)
        counts: dict[str, int] = {"users": len(builder.users)}
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
    parser = argparse.ArgumentParser(description="Siembra datos de demostracion para las BQ")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--weeks", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run(args.seed, args.weeks, args.dry_run)
    except ImportFailure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
