import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from app import models, schemas, section_catalog
from app.database import get_db
from app.security import get_current_user

router = APIRouter(prefix="/analytics/sections", tags=["section-usage"])


def require_analytics_admin(user: models.User = Depends(get_current_user)) -> models.User:
    allowed = {
        email.strip().lower()
        for email in os.environ.get("ANALYTICS_ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    if user.email.lower() not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Analytics access denied")
    return user


def _as_utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _window(start: datetime | None, end: datetime | None):
    conditions = []
    if start is not None:
        conditions.append(models.SectionEvent.client_timestamp >= _as_utc(start))
    if end is not None:
        conditions.append(models.SectionEvent.client_timestamp < _as_utc(end))
    return conditions


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _section_metrics(db: Session, start: datetime | None, end: datetime | None) -> dict:
    event = models.SectionEvent
    window = _window(start, end)

    def counts(event_type: str) -> dict[str, int]:
        rows = db.execute(
            select(event.section, func.count())
            .where(event.event_type == event_type, *window)
            .group_by(event.section)
        ).all()
        return {section: total for section, total in rows}

    views = counts(section_catalog.SECTION_VIEW)
    interactions = counts(section_catalog.SECTION_INTERACTION)

    unique_users = {
        section: total
        for section, total in db.execute(
            select(event.section, func.count(distinct(event.user_id)))
            .where(*window)
            .group_by(event.section)
        ).all()
    }

    view_alias = select(event.section, event.visit_id).where(
        event.event_type == section_catalog.SECTION_VIEW, *window
    ).subquery()
    engaged_rows = db.execute(
        select(event.section, func.count(distinct(event.visit_id)))
        .join(
            view_alias,
            and_(view_alias.c.section == event.section, view_alias.c.visit_id == event.visit_id),
        )
        .where(event.event_type == section_catalog.SECTION_INTERACTION, *window)
        .group_by(event.section)
    ).all()
    engaged_visits = {section: total for section, total in engaged_rows}

    total_views = sum(views.values())
    total_interactions = sum(interactions.values())

    sections = {}
    for name in section_catalog.SECTIONS:
        section_views = views.get(name, 0)
        section_interactions = interactions.get(name, 0)
        sections[name] = {
            "section": name,
            "visits": section_views,
            "interactions": section_interactions,
            "unique_users": unique_users.get(name, 0),
            "interactions_per_visit": _ratio(section_interactions, section_views),
            "visits_with_interaction": engaged_visits.get(name, 0),
            "interaction_rate": _ratio(engaged_visits.get(name, 0), section_views),
            "share_of_visits": _ratio(section_views, total_views),
            "share_of_interactions": _ratio(section_interactions, total_interactions),
            "sufficient_data": section_views >= section_catalog.MIN_VISITS_PER_SECTION,
        }
    return sections


def _classify(sections: dict) -> dict:
    reliable = [m for m in sections.values() if m["sufficient_data"]]
    classification = {}
    if not reliable:
        for name in sections:
            classification[name] = "insufficient_data"
        return classification
    mean_visits = sum(m["visits"] for m in reliable) / len(reliable)
    mean_rate = sum(m["interaction_rate"] for m in reliable) / len(reliable)
    for name, metrics in sections.items():
        if not metrics["sufficient_data"]:
            classification[name] = "insufficient_data"
            continue
        low_discovery = metrics["visits"] < section_catalog.LOW_USE_RATIO * mean_visits
        low_engagement = metrics["interaction_rate"] < section_catalog.LOW_USE_RATIO * mean_rate
        if low_discovery and low_engagement:
            classification[name] = "low_use"
        elif low_discovery:
            classification[name] = "niche_high_engagement"
        elif low_engagement:
            classification[name] = "low_engagement"
        else:
            classification[name] = "healthy"
    return classification


RECOMMENDATIONS = {
    "low_use": ["run_user_research", "simplify_or_relocate", "removal_only_after_research"],
    "low_engagement": ["redesign_content_or_controls", "run_user_research"],
    "niche_high_engagement": ["improve_discoverability", "relocate_in_navigation"],
    "healthy": [],
    "insufficient_data": ["collect_more_data"],
}


def _ranking(sections: dict, key: str) -> list[dict]:
    ranked = [m for m in sections.values() if m[key] is not None]
    ranked.sort(key=lambda m: (m[key], m["section"]))
    return [{"section": m["section"], key: m[key]} for m in ranked]


def _least(sections: dict, key: str) -> str | None:
    reliable = [m for m in sections.values() if m["sufficient_data"]]
    if not reliable:
        return None
    return min(reliable, key=lambda m: (m[key], m["section"]))["section"]


@router.post("/events", response_model=schemas.SectionEventsAccepted)
def record_section_events(
    batch: schemas.SectionEventBatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    accepted = 0
    for item in batch.events:
        statement = (
            postgres_insert(models.SectionEvent)
            .values(
                event_id=item.event_id,
                event_type=item.event_type,
                section=item.section,
                action=item.action,
                visit_id=item.visit_id,
                user_id=user.id,
                client_timestamp=item.client_timestamp,
                extra=item.extra,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
            .returning(models.SectionEvent.event_id)
        )
        if db.execute(statement).first() is not None:
            accepted += 1
    db.commit()
    return {"accepted": accepted, "duplicates": len(batch.events) - accepted}


@router.get("/usage")
def section_usage(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_analytics_admin),
):
    sections = _section_metrics(db, start, end)
    classification = _classify(sections)
    return {
        "window": {"start": start, "end": end},
        "min_visits_per_section": section_catalog.MIN_VISITS_PER_SECTION,
        "total_visits": sum(m["visits"] for m in sections.values()),
        "total_interactions": sum(m["interactions"] for m in sections.values()),
        "sections": [
            {**metrics, "classification": classification[name]}
            for name, metrics in sections.items()
        ],
    }


@router.get("/least-used")
def least_used_sections(
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_analytics_admin),
):
    sections = _section_metrics(db, start, end)
    classification = _classify(sections)
    enough_data = all(m["sufficient_data"] for m in sections.values())
    return {
        "window": {"start": start, "end": end},
        "min_visits_per_section": section_catalog.MIN_VISITS_PER_SECTION,
        "sufficient_data": enough_data,
        "ranking_by_visits": _ranking(sections, "visits"),
        "ranking_by_interactions": _ranking(sections, "interactions"),
        "ranking_by_interaction_rate": _ranking(sections, "interaction_rate"),
        "sections": [
            {
                "section": name,
                "classification": classification[name],
                "recommendations": RECOMMENDATIONS[classification[name]],
            }
            for name in section_catalog.SECTIONS
        ],
        "least_visited": _least(sections, "visits"),
        "least_interaction_rate": _least(sections, "interaction_rate"),
    }
