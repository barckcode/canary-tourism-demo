"""Time series data endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import TimeSeries
from app.rate_limit import limiter

router = APIRouter()

# Indicators used for Year-over-Year heatmap calculations
YOY_INDICATORS = [
    "turistas",
    "alojatur_ocupacion",
    "alojatur_adr",
    "alojatur_revpar",
    "alojatur_pernoctaciones",
]


@router.get("")
@limiter.limit("60/minute")
def get_timeseries(
    request: Request,
    indicator: str = Query(..., description="Indicator name"),
    geo: str = Query("ES709", description="Geographic code"),
    from_period: str = Query(None, alias="from", description="Start period YYYY-MM"),
    to_period: str = Query(None, alias="to", description="End period YYYY-MM"),
    measure: str = Query("ABSOLUTE", description="Measure type"),
    db: Session = Depends(get_db),
):
    """Return time series data for a given indicator and geography."""
    q = db.query(TimeSeries).filter(
        TimeSeries.indicator == indicator,
        TimeSeries.geo_code == geo,
        TimeSeries.measure == measure,
    )
    if from_period:
        q = q.filter(TimeSeries.period >= from_period)
    if to_period:
        q = q.filter(TimeSeries.period <= to_period)

    results = q.order_by(TimeSeries.period).all()

    return {
        "data": [{"period": r.period, "value": r.value} for r in results],
        "metadata": {
            "indicator": indicator,
            "geo": geo,
            "measure": measure,
            "total_points": len(results),
        },
    }


@router.get("/indicators")
@limiter.limit("60/minute")
def list_indicators(request: Request, db: Session = Depends(get_db)):
    """Return list of available indicators with metadata."""
    from sqlalchemy import func

    rows = (
        db.query(
            TimeSeries.indicator,
            TimeSeries.source,
            func.min(TimeSeries.period).label("available_from"),
            func.max(TimeSeries.period).label("available_to"),
            func.count(TimeSeries.id).label("total_points"),
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
        }
        for r in rows
    ]


@router.get("/yoy")
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
