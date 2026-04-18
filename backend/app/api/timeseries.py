"""Time series data endpoints."""

import math
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    IndicatorInfo,
    TimeSeriesPaginatedResponse,
    TimeSeriesResponse,
    YoYResponse,
)
from app.db.database import get_db
from app.db.models import TimeSeries
from app.rate_limit import limiter

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_period(value: str | None, name: str) -> str | None:
    """Validate that a period string matches YYYY-MM format.

    Raises HTTPException(400) if the format is invalid.
    """
    if value is None:
        return None
    if not PERIOD_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {name} format. Use YYYY-MM (e.g., 2026-03)",
        )
    return value

router = APIRouter()

# Indicators used for Year-over-Year heatmap calculations
YOY_INDICATORS = [
    "turistas",
    "alojatur_ocupacion",
    "alojatur_adr",
    "alojatur_revpar",
    "alojatur_pernoctaciones",
]


@router.get("", response_model=TimeSeriesPaginatedResponse)
@limiter.limit("60/minute")
def get_timeseries(
    request: Request,
    indicator: str = Query(..., description="Indicator name"),
    geo: str = Query("ES709", description="Geographic code"),
    from_period: str = Query(None, alias="from", description="Start period YYYY-MM"),
    to_period: str = Query(None, alias="to", description="End period YYYY-MM"),
    measure: str = Query("ABSOLUTE", description="Measure type"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page (1-500)"),
    db: Session = Depends(get_db),
):
    """Return paginated time series data for a given indicator and geography.

    Supports pagination via ``page`` and ``page_size`` query parameters.
    The response includes a ``pagination`` object with total count,
    current page, page size, and total pages.
    """
    _validate_period(from_period, "from_period")
    _validate_period(to_period, "to_period")

    if from_period and to_period and from_period > to_period:
        raise HTTPException(
            status_code=400,
            detail="'from' period must be before or equal to 'to' period",
        )

    q = db.query(TimeSeries).filter(
        TimeSeries.indicator == indicator,
        TimeSeries.geo_code == geo,
        TimeSeries.measure == measure,
    )
    if from_period:
        q = q.filter(TimeSeries.period >= from_period)
    if to_period:
        q = q.filter(TimeSeries.period <= to_period)

    total = q.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    results = (
        q.order_by(TimeSeries.period)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "data": [{"period": r.period, "value": r.value} for r in results if r.value is not None],
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@router.get("/indicators", response_model=list[IndicatorInfo])
@limiter.limit("60/minute")
def list_indicators(request: Request, db: Session = Depends(get_db)):
    """Return list of available indicators with metadata.

    Each indicator includes a ``last_updated`` field derived from the most
    recent ``fetched_at`` timestamp in the time_series table, indicating
    when data for that indicator was last refreshed by the ETL pipeline.
    """
    from sqlalchemy import func

    rows = (
        db.query(
            TimeSeries.indicator,
            TimeSeries.source,
            func.min(TimeSeries.period).label("available_from"),
            func.max(TimeSeries.period).label("available_to"),
            func.count(TimeSeries.id).label("total_points"),
            func.max(TimeSeries.fetched_at).label("last_updated"),
        )
        .group_by(TimeSeries.indicator, TimeSeries.source)
        .all()
    )

    return [
        {
            "id": r.indicator,
            "source": r.source,
            "available_from": r.available_from,
            "available_to": r.available_to,
            "total_points": r.total_points,
            "last_updated": r.last_updated,
        }
        for r in rows
    ]


@router.get("/yoy", response_model=YoYResponse)
@limiter.limit("60/minute")
def get_yoy(
    request: Request,
    indicator: Optional[str] = Query(
        None,
        description=(
            "Single indicator to compute YoY for. "
            "If omitted, returns all main indicators."
        ),
    ),
    geo: str = Query("ES709", description="Geographic code"),
    db: Session = Depends(get_db),
):
    """Return year-over-year percentage change per indicator, year and month.

    For each indicator the endpoint fetches all monthly values from the
    ``time_series`` table, groups them by year and month, and computes the
    percentage change relative to the same month of the previous year.

    The response is keyed by indicator name.  Each entry contains a list of
    cell objects with ``year``, ``month`` (0-based), ``value`` (the raw
    observation) and ``yoy_change`` (percentage change vs. the same month of
    the prior year, or ``null`` when no prior-year data is available).
    """
    indicators = [indicator] if indicator else YOY_INDICATORS

    result: dict = {}

    for ind in indicators:
        rows = (
            db.query(TimeSeries)
            .filter(
                TimeSeries.indicator == ind,
                TimeSeries.geo_code == geo,
                TimeSeries.measure == "ABSOLUTE",
            )
            .order_by(TimeSeries.period)
            .all()
        )

        if not rows:
            continue

        # Build lookup: {(year, month): value}
        lookup: dict[tuple[int, int], float] = {}
        for r in rows:
            # period format is "YYYY-MM"
            parts = r.period.split("-")
            if len(parts) < 2:
                continue
            try:
                year = int(parts[0])
                month = int(parts[1]) - 1  # 0-based for frontend
            except (ValueError, IndexError):
                continue
            if r.value is not None:
                lookup[(year, month)] = r.value

        # Compute YoY change for each (year, month)
        cells = []
        for (year, month), value in sorted(lookup.items()):
            prev_value = lookup.get((year - 1, month))
            yoy_change = None
            if prev_value is not None and prev_value != 0:
                yoy_change = round(((value - prev_value) / prev_value) * 100, 2)

            cells.append(
                {
                    "year": year,
                    "month": month,
                    "value": value,
                    "yoy_change": yoy_change,
                }
            )

        if cells:
            result[ind] = cells

    return {
        "indicators": result,
        "metadata": {
            "geo": geo,
            "total_indicators": len(result),
        },
    }
