"""Dashboard KPI and summary endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Prediction, TimeSeries

router = APIRouter()


@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db)):
    """Return latest KPI values for the dashboard."""
    kpis = {}

    # Latest arrivals
    latest = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator == "turistas",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .first()
    )
    if latest:
        kpis["latest_arrivals"] = latest.value
        kpis["latest_period"] = latest.period

        # YoY change
        prev_year_period = f"{int(latest.period[:4]) - 1}{latest.period[4:]}"
        prev = (
            db.query(TimeSeries)
            .filter(
                TimeSeries.indicator == "turistas",
                TimeSeries.geo_code == "ES709",
                TimeSeries.measure == "ABSOLUTE",
                TimeSeries.period == prev_year_period,
            )
            .first()
        )
        if prev and prev.value:
            kpis["yoy_change"] = round(
                (latest.value - prev.value) / prev.value * 100, 2
            )

    # Occupancy rate
    occ = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator == "alojatur_habitaciones_ocupacion",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .first()
    )
    if occ:
        kpis["occupancy_rate"] = occ.value

    # ADR
    adr = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator == "alojatur_ingresos_habitacion",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .first()
    )
    if adr:
        kpis["adr"] = adr.value

    # RevPAR (income per available room)
    revpar = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator == "alojatur_ingresos",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .first()
    )
    if revpar:
        kpis["revpar"] = revpar.value

    # Average stay
    avg_stay = (
        db.query(TimeSeries)
        .filter(
            TimeSeries.indicator == "alojatur_estancias_medias",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .first()
    )
    if avg_stay:
        kpis["avg_stay"] = avg_stay.value

    # Last updated
    last_fetched = db.query(func.max(TimeSeries.fetched_at)).scalar()
    kpis["last_updated"] = last_fetched

    return kpis


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Return 12-month trend data and top nationalities for the dashboard."""
    # Arrivals trend (last 24 months)
    arrivals = (
        db.query(TimeSeries.period, TimeSeries.value)
        .filter(
            TimeSeries.indicator == "turistas",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .limit(24)
        .all()
    )
    arrivals_trend = [
        {"period": r.period, "value": r.value}
        for r in reversed(arrivals)
    ]

    # Occupancy trend (last 12 months)
    occupancy = (
        db.query(TimeSeries.period, TimeSeries.value)
        .filter(
            TimeSeries.indicator == "alojatur_habitaciones_ocupacion",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .limit(12)
        .all()
    )
    occupancy_trend = [
        {"period": r.period, "value": r.value}
        for r in reversed(occupancy)
    ]

    # Latest ensemble forecast
    forecasts = (
        db.query(Prediction.period, Prediction.value_predicted)
        .filter(
            Prediction.model == "ensemble",
            Prediction.indicator == "turistas",
        )
        .order_by(Prediction.period)
        .all()
    )
    forecast_trend = [
        {"period": r.period, "value": r.value_predicted}
        for r in forecasts
    ]

    return {
        "arrivals_trend_24m": arrivals_trend,
        "occupancy_trend_12m": occupancy_trend,
        "forecast": forecast_trend,
    }
