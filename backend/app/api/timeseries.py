"""Time series data endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import TimeSeries
from app.rate_limit import limiter

router = APIRouter()


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
