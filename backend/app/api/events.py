"""Tourism event calendar endpoints.

Provides CRUD operations for tourism events that can be overlaid on
time series charts to correlate arrivals data with known events.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateEventRequest,
    EventListResponse,
    EventResponse,
)
from app.db.database import get_db
from app.db.models import TourismEvent
from app.rate_limit import limiter

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
