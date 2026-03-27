"""Tourism event calendar endpoints.

Provides CRUD operations for tourism events that can be overlaid on
time series charts to correlate arrivals data with known events.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateEventRequest,
    EventImpactResponse,
    EventKPI,
    EventListResponse,
    EventResponse,
)
from app.db.database import get_db
from app.db.models import TimeSeries, TourismEvent
from app.rate_limit import limiter

DATE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _validate_date(value: str | None, name: str) -> str | None:
    """Validate that a date string matches YYYY-MM-DD format.

    Raises HTTPException(400) if the format is invalid.
    """
    if value is None:
        return None
    if not DATE_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name} format. Use YYYY-MM-DD (e.g., 2026-03-15)",
        )
    return value


router = APIRouter()


def _to_response(row: TourismEvent) -> EventResponse:
    return EventResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        category=row.category,
        start_date=row.start_date,
        end_date=row.end_date,
        impact_estimate=row.impact_estimate,
        location=row.location,
        source=row.source,
        created_at=row.created_at,
    )


@router.get("", response_model=EventListResponse)
@limiter.limit("30/minute")
def list_events(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """List events, optionally filtered by date range and category.

    - **from_date**: filter events whose start_date >= this value (YYYY-MM-DD)
    - **to_date**: filter events whose start_date <= this value (YYYY-MM-DD)
    - **category**: filter by event category (cultural, connectivity, regulation, external)
    """
    _validate_date(from_date, "from_date")
    _validate_date(to_date, "to_date")

    query = db.query(TourismEvent)

    if from_date:
        # Include events that overlap with the range: end_date >= from_date or
        # single-day events with start_date >= from_date
        query = query.filter(
            (TourismEvent.end_date >= from_date) | (
                (TourismEvent.end_date.is_(None)) & (TourismEvent.start_date >= from_date)
            )
        )

    if to_date:
        query = query.filter(TourismEvent.start_date <= to_date)

    if category:
        query = query.filter(TourismEvent.category == category)

    rows = query.order_by(TourismEvent.start_date).all()
    return EventListResponse(events=[_to_response(r) for r in rows])


@router.get("/categories")
@limiter.limit("30/minute")
def list_categories(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return distinct event categories."""
    rows = db.query(distinct(TourismEvent.category)).order_by(TourismEvent.category).all()
    return {"categories": [r[0] for r in rows]}


def _date_to_monthly_periods(start_date: str, end_date: str | None) -> list[str]:
    """Convert a date range to a list of YYYY-MM monthly period strings."""
    start_ym = start_date[:7]  # "YYYY-MM"
    if end_date:
        end_ym = end_date[:7]
    else:
        end_ym = start_ym

    periods: list[str] = []
    current = start_ym
    while current <= end_ym:
        periods.append(current)
        # Advance to next month
        year, month = int(current[:4]), int(current[5:7])
        month += 1
        if month > 12:
            month = 1
            year += 1
        current = f"{year}-{month:02d}"
    return periods


def _shift_periods_by_year(periods: list[str], delta: int) -> list[str]:
    """Shift each YYYY-MM period by *delta* years."""
    shifted: list[str] = []
    for p in periods:
        year, month = int(p[:4]), int(p[5:7])
        shifted.append(f"{year + delta}-{month:02d}")
    return shifted


_IMPACT_INDICATORS = [
    "turistas",
    "alojatur_ocupacion",
    "alojatur_adr",
    "alojatur_revpar",
    "alojatur_pernoctaciones",
]


@router.get("/{event_id}/impact", response_model=EventImpactResponse)
@limiter.limit("30/minute")
def get_event_impact(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
):
    """Analyse the KPI impact of a tourism event.

    Returns current-year and previous-year KPI values for the monthly
    periods covered by the event, together with year-over-year percentage
    changes for each indicator.

    - **event_id**: ID of the tourism event to analyse
    """
    event = db.query(TourismEvent).filter(TourismEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    periods = _date_to_monthly_periods(event.start_date, event.end_date)
    prev_periods = _shift_periods_by_year(periods, -1)

    # Query current-year KPIs
    current_rows = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator.in_(_IMPACT_INDICATORS),
            TimeSeries.geo_code.like("%ES70%"),
            TimeSeries.period.in_(periods),
        )
        .all()
    )

    # Query previous-year KPIs
    prev_rows = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator.in_(_IMPACT_INDICATORS),
            TimeSeries.geo_code.like("%ES70%"),
            TimeSeries.period.in_(prev_periods),
        )
        .all()
    )

    current_kpis = [
        EventKPI(indicator=r.indicator, period=r.period, value=r.value)
        for r in current_rows
    ]
    previous_year_kpis = [
        EventKPI(indicator=r.indicator, period=r.period, value=r.value)
        for r in prev_rows
    ]

    # Calculate YoY % change per indicator (average across periods)
    def _avg_by_indicator(rows: list) -> dict[str, float]:
        totals: dict[str, list[float]] = {}
        for r in rows:
            if r.value is not None:
                totals.setdefault(r.indicator, []).append(r.value)
        return {k: sum(v) / len(v) for k, v in totals.items()}

    curr_avgs = _avg_by_indicator(current_rows)
    prev_avgs = _avg_by_indicator(prev_rows)

    yoy_changes: dict[str, float | None] = {}
    for ind in _IMPACT_INDICATORS:
        curr_val = curr_avgs.get(ind)
        prev_val = prev_avgs.get(ind)
        if curr_val is not None and prev_val is not None and prev_val != 0:
            yoy_changes[ind] = round((curr_val - prev_val) / prev_val * 100, 2)
        else:
            yoy_changes[ind] = None

    return EventImpactResponse(
        event_id=event.id,
        event_name=event.name,
        start_date=event.start_date,
        end_date=event.end_date or event.start_date,
        category=event.category,
        current_kpis=current_kpis,
        previous_year_kpis=previous_year_kpis,
        yoy_changes=yoy_changes,
    )


@router.post("", response_model=EventResponse, status_code=201)
@limiter.limit("20/minute")
def create_event(
    request: Request,
    body: CreateEventRequest,
    db: Session = Depends(get_db),
):
    """Create a custom tourism event.

    Custom events are always created with source='user' and can be deleted
    later. System-seeded events cannot be created through this endpoint.
    """
    event = TourismEvent(
        name=body.name,
        description=body.description,
        category=body.category,
        start_date=body.start_date,
        end_date=body.end_date,
        impact_estimate=body.impact_estimate,
        location=body.location,
        source="user",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _to_response(event)


@router.delete("/{event_id}", status_code=204)
@limiter.limit("20/minute")
def delete_event(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
):
    """Delete a tourism event (only user-created events can be deleted).

    System-seeded events (source='system') are protected and cannot be removed.
    """
    event = db.query(TourismEvent).filter(TourismEvent.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.source != "user":
        raise HTTPException(
            status_code=403,
            detail="Only user-created events can be deleted",
        )
    db.delete(event)
    db.commit()
