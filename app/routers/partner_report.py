import csv
import io
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.routers.section_usage import require_analytics_admin

router = APIRouter(prefix="/analytics/partner-report", tags=["partner-report"])

MIN_REVIEWS_FOR_COMPLAINTS = 3  
MIN_MENTIONS_RECURRING = 2      
POSITIVE_FROM = 4.0             
NEGATIVE_BELOW = 3.0            
LOW_SCORE = 2                  

THEMES: dict[str, tuple[str, str | None, tuple[str, ...]]] = {
    "taste": ("Taste & food quality", "taste",
              ("cold", "frio", "fria", "bland", "sin sabor", "insipid", "stale", "greasy", "grasos", "crudo", "mal sabor")),
    "service": ("Service & attention", "attention",
                ("rude", "grosero", "mala atencion", "mal servicio", "ignored", "ignoraron", "mal trato")),
    "wait": ("Long waits", None,
             ("slow", "lento", "lenta", "demora", "demoro", "wait", "espera", "esperar", "fila", "queue", "long line")),
    "price": ("Value for money", "price",
              ("expensive", "caro", "cara", "costoso", "overpriced", "pricey", "muy caro")),
    "options": ("Dietary options", "options",
                ("no options", "sin opciones", "pocas opciones", "limited", "limitado", "no vegan", "no vegetarian", "sin gluten")),
    "hygiene": ("Hygiene", None,
                ("dirty", "sucio", "sucia", "hair", "cabello", "pelo", "hygiene", "higiene", "cucaracha", "bug")),
    "crowding": ("Crowding", None,
                 ("crowded", "lleno", "llena", "abarrotado", "no seat", "sin puesto", "sin mesa")),
}



_PATTERNS = {
    theme: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b")
    for theme, (_, _, keywords) in THEMES.items()
}


class VisitVolume(BaseModel):
    views: int
    unique_visitors: int
    go_decisions: int
    go_rate: float | None           
    previous_views: int
    views_change_pct: float | None  


class Sentiment(BaseModel):
    review_count: int
    avg_overall: float | None
    label: str                      
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    previous_avg_overall: float | None
    avg_change: float | None
    category_averages: dict[str, float | None]


class Complaint(BaseModel):
    theme: str
    label: str
    mentions: int
    share_pct: float                


class PartnerReportOut(BaseModel):
    restaurant_id: str
    restaurant_name: str
    period_days: int
    period_start: datetime
    period_end: datetime
    visits: VisitVolume
    sentiment: Sentiment
    complaints: list[Complaint]
    complaints_hidden: bool         
    highlights: list[str]           


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  


def _normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in stripped if unicodedata.category(c) != "Mn")


def _pct(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total else 0.0


def _overall(r: models.Review) -> float:
    return (r.taste + r.attention + r.price + r.options) / 4.0


def _visits(db: Session, restaurant_id: str, start: datetime, end: datetime, prev_start: datetime) -> VisitVolume:
    view = models.RestaurantView

    def views_between(a: datetime, b: datetime) -> int:
        return (
            db.query(func.count(view.id))
            .filter(view.restaurant_id == restaurant_id, view.viewed_at >= a, view.viewed_at < b)
            .scalar()
        ) or 0

    views = views_between(start, end)
    previous = views_between(prev_start, start)
    unique = (
        db.query(func.count(distinct(view.user_id)))
        .filter(view.restaurant_id == restaurant_id, view.viewed_at >= start, view.viewed_at < end)
        .scalar()
    ) or 0
    go = (
        db.query(func.count(models.PlaceSelectionEvent.id))
        .filter(
            models.PlaceSelectionEvent.restaurant_id == restaurant_id,
            models.PlaceSelectionEvent.received_at >= start,
            models.PlaceSelectionEvent.received_at < end,
        )
        .scalar()
    ) or 0
    return VisitVolume(
        views=views,
        unique_visitors=unique,
        go_decisions=go,
        go_rate=round(go / views, 4) if views else None,
        previous_views=previous,
        views_change_pct=round((views - previous) * 100 / previous, 1) if previous else None,
    )


def _reviews_between(db: Session, restaurant_id: str, start: datetime, end: datetime) -> list[models.Review]:
    return (
        db.query(models.Review)
        .filter(
            models.Review.restaurant_id == restaurant_id,
            models.Review.created_at >= start,
            models.Review.created_at < end,
        )
        .all()
    )


def _sentiment(reviews: list[models.Review], previous: list[models.Review]) -> Sentiment:
    n = len(reviews)
    overalls = [_overall(r) for r in reviews]
    avg = round(sum(overalls) / n, 2) if n else None
    prev_avg = round(sum(_overall(r) for r in previous) / len(previous), 2) if previous else None
    positive = sum(1 for o in overalls if o >= POSITIVE_FROM)
    negative = sum(1 for o in overalls if o < NEGATIVE_BELOW)
    neutral = n - positive - negative
    if avg is None:
        label = "no_data"
    elif avg >= POSITIVE_FROM:
        label = "positive"
    elif avg >= NEGATIVE_BELOW:
        label = "mixed"
    else:
        label = "negative"
    categories = {
        key: round(sum(getattr(r, key) for r in reviews) / n, 2) if n else None
        for key in ("taste", "attention", "price", "options")
    }
    return Sentiment(
        review_count=n,
        avg_overall=avg,
        label=label,
        positive_pct=_pct(positive, n),
        neutral_pct=_pct(neutral, n),
        negative_pct=_pct(negative, n),
        previous_avg_overall=prev_avg,
        avg_change=round(avg - prev_avg, 2) if avg is not None and prev_avg is not None else None,
        category_averages=categories,
    )


def _complaints(reviews: list[models.Review]) -> list[Complaint]:
    counts = {theme: 0 for theme in THEMES}
    for r in reviews:
        text = _normalize(r.comment or "")
        not_positive = _overall(r) < POSITIVE_FROM  
        for theme, (_, category, _keywords) in THEMES.items():
            low_category = category is not None and getattr(r, category) <= LOW_SCORE
            keyword_hit = not_positive and _PATTERNS[theme].search(text) is not None
            if low_category or keyword_hit:
                counts[theme] += 1
    complaints = [
        Complaint(theme=t, label=THEMES[t][0], mentions=c, share_pct=_pct(c, len(reviews)))
        for t, c in counts.items()
        if c >= MIN_MENTIONS_RECURRING
    ]
    return sorted(complaints, key=lambda c: c.mentions, reverse=True)


def _highlights(visits: VisitVolume, sentiment: Sentiment, complaints: list[Complaint], days: int) -> list[str]:
    notes = []
    if visits.views_change_pct is not None:
        direction = "up" if visits.views_change_pct >= 0 else "down"
        notes.append(f"Visits are {direction} {abs(visits.views_change_pct)}% vs. the previous {days} days.")
    elif visits.views:
        notes.append(f"{visits.views} visits in the last {days} days (no data for the previous period).")
    if sentiment.avg_overall is not None:
        notes.append(
            f"Overall sentiment is {sentiment.label}: {sentiment.avg_overall}/5 "
            f"({sentiment.positive_pct}% positive, {sentiment.negative_pct}% negative)."
        )
    if complaints:
        top = complaints[0]
        notes.append(f"Most recurring complaint: {top.label} ({top.mentions} reviews, {top.share_pct}%).")
    return notes


def build_report(db: Session, restaurant_id: str, days: int) -> PartnerReportOut:
    restaurant = db.get(models.Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(404, "Restaurant not found")
    end = _now()
    start = end - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    visits = _visits(db, restaurant_id, start, end, prev_start)
    reviews = _reviews_between(db, restaurant_id, start, end)
    previous = _reviews_between(db, restaurant_id, prev_start, start)
    sentiment = _sentiment(reviews, previous)
    hidden = len(reviews) < MIN_REVIEWS_FOR_COMPLAINTS
    complaints = [] if hidden else _complaints(reviews)
    return PartnerReportOut(
        restaurant_id=restaurant_id,
        restaurant_name=restaurant.name,
        period_days=days,
        period_start=start.replace(tzinfo=timezone.utc),
        period_end=end.replace(tzinfo=timezone.utc),
        visits=visits,
        sentiment=sentiment,
        complaints=complaints,
        complaints_hidden=hidden,
        highlights=_highlights(visits, sentiment, complaints, days),
    )


@router.get("/{restaurant_id}", response_model=PartnerReportOut)
def get_partner_report(
    restaurant_id: str,
    days: int = Query(default=30, ge=7, le=180),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_analytics_admin),
):
    return build_report(db, restaurant_id, days)


@router.get("/{restaurant_id}/export")
def export_partner_report(
    restaurant_id: str,
    days: int = Query(default=30, ge=7, le=180),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_analytics_admin),
):
    report = build_report(db, restaurant_id, days)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "metric", "value"])
    writer.writerow(["info", "restaurant", report.restaurant_name])
    writer.writerow(["info", "period_days", report.period_days])
    for key, value in report.visits.model_dump().items():
        writer.writerow(["visits", key, value])
    for key, value in report.sentiment.model_dump().items():
        if key != "category_averages":
            writer.writerow(["sentiment", key, value])
    for key, value in report.sentiment.category_averages.items():
        writer.writerow(["sentiment", f"avg_{key}", value])
    for c in report.complaints:
        writer.writerow(["complaints", c.label, f"{c.mentions} ({c.share_pct}%)"])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=partner_report_{restaurant_id}.csv"},
    )