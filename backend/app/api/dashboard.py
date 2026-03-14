"""Dashboard KPI and summary endpoints."""

import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.schemas import (
    DashboardKPIsResponse,
    DashboardSummaryResponse,
    SeasonalPositionResponse,
    TopMarketsResponse,
)
from app.db.database import get_db
from app.db.models import Microdata, Prediction, TimeSeries
from app.rate_limit import limiter

# EGT/ISTAC nationality codes to human-readable names (same as profiles.py)
NATIONALITY_LABELS = {
    "826": "United Kingdom",
    "276": "Germany",
    "250": "France",
    "380": "Italy",
    "724_XES70": "Spain (mainland)",
    "528": "Netherlands",
    "372": "Ireland",
    "056": "Belgium",
    "756": "Switzerland",
    "154_L1": "Nordic Countries",
    "001_O": "Other",
    "840": "United States",
    "616": "Poland",
    "203": "Czech Republic",
    "620": "Portugal",
    "040": "Austria",
    "643": "Russia",
    "752": "Sweden",
    "246": "Finland",
    "208": "Denmark",
    "578": "Norway",
}

router = APIRouter()


@router.get("/kpis", response_model=DashboardKPIsResponse)
@limiter.limit("60/minute")
def get_kpis(request: Request, db: Session = Depends(get_db)):
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
    if latest and latest.value is not None:
        kpis["latest_arrivals"] = latest.value
        kpis["latest_period"] = latest.period

        # YoY change — guard against malformed period strings
        if latest.period and len(latest.period) >= 4:
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
            if prev is not None and prev.value is not None and prev.value != 0:
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

    if not kpis or "latest_arrivals" not in kpis:
        raise HTTPException(
            status_code=404,
            detail="No KPI data available. The database may not have been populated yet.",
        )

    return kpis


@router.get("/summary", response_model=DashboardSummaryResponse)
@limiter.limit("60/minute")
def get_summary(request: Request, db: Session = Depends(get_db)):
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

    if not arrivals_trend:
        raise HTTPException(
            status_code=404,
            detail="No arrivals trend data available. The database may not have been populated yet.",
        )

    return {
        "arrivals_trend_24m": arrivals_trend,
        "occupancy_trend_12m": occupancy_trend,
        "forecast": forecast_trend,
    }


@router.get("/top-markets", response_model=TopMarketsResponse)
@limiter.limit("60/minute")
def get_top_markets(request: Request, db: Session = Depends(get_db)):
    """Return top 5 source markets by tourist count from microdata.

    Aggregates nationality data from the microdata table and returns
    each market's share as a percentage of the total.
    """
    results = (
        db.query(
            Microdata.nacionalidad,
            func.count(Microdata.id).label("count"),
        )
        .filter(Microdata.nacionalidad.isnot(None))
        .group_by(Microdata.nacionalidad)
        .order_by(func.count(Microdata.id).desc())
        .all()
    )

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No microdata available to compute top markets.",
        )

    total = sum(r.count for r in results)
    markets = []
    for r in results[:5]:
        pct = round(r.count / total * 100, 1) if total > 0 else 0
        markets.append({
            "country": NATIONALITY_LABELS.get(r.nacionalidad, r.nacionalidad),
            "code": r.nacionalidad,
            "pct": pct,
            "count": r.count,
        })

    return {"markets": markets, "total": total}


@router.get("/seasonal-position", response_model=SeasonalPositionResponse)
@limiter.limit("60/minute")
def get_seasonal_position(request: Request, db: Session = Depends(get_db)):
    """Return seasonal position analysis for the dashboard.

    Computes:
    - peak_month: the month with the highest average arrivals historically
    - current_position: how the current month compares to historical average
      (High / Moderate / Low)
    - next_3_months: forecast-based outlook for the next 3 months
    """
    # Get all monthly arrivals to compute seasonal averages
    arrivals = (
        db.query(TimeSeries.period, TimeSeries.value)
        .filter(
            TimeSeries.indicator == "turistas",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
            TimeSeries.value.isnot(None),
        )
        .all()
    )

    if not arrivals:
        raise HTTPException(
            status_code=404,
            detail="No arrivals data available for seasonal analysis.",
        )

    # Group values by month number (1-12)
    monthly_sums: dict[int, float] = {}
    monthly_counts: dict[int, int] = {}
    for row in arrivals:
        # period format is "YYYY-MM" or "YYYYMM"
        period_str = row.period.replace("-", "")
        if len(period_str) >= 6:
            month = int(period_str[4:6])
            if 1 <= month <= 12:
                monthly_sums[month] = monthly_sums.get(month, 0) + row.value
                monthly_counts[month] = monthly_counts.get(month, 0) + 1

    if not monthly_sums:
        raise HTTPException(
            status_code=404,
            detail="Could not parse monthly data for seasonal analysis.",
        )

    # Compute monthly averages
    monthly_avg: dict[int, float] = {
        m: monthly_sums[m] / monthly_counts[m] for m in monthly_sums
    }

    # Peak month
    peak_month_num = max(monthly_avg, key=monthly_avg.get)  # type: ignore[arg-type]
    peak_month_name = calendar.month_name[peak_month_num]

    # Overall average across all months
    overall_avg = sum(monthly_avg.values()) / len(monthly_avg)

    # Current month position
    current_month = date.today().month
    current_avg = monthly_avg.get(current_month, overall_avg)
    current_position = _classify_position(current_avg, overall_avg)

    # Next 3 months outlook using ensemble forecast from predictions table
    next_months = [(current_month % 12) + i for i in range(1, 4)]
    next_months = [((m - 1) % 12) + 1 for m in next_months]

    # Try to get forecast values for next 3 months
    forecasts = (
        db.query(Prediction.period, Prediction.value_predicted)
        .filter(
            Prediction.model == "ensemble",
            Prediction.indicator == "turistas",
        )
        .order_by(Prediction.period)
        .all()
    )

    next_3_values = []
    if forecasts:
        # Build a lookup of forecast values by month number
        for fc in forecasts:
            fc_period = fc.period.replace("-", "")
            if len(fc_period) >= 6:
                fc_month = int(fc_period[4:6])
                if fc_month in next_months:
                    next_3_values.append(fc.value_predicted)

    if next_3_values:
        avg_next_3 = sum(next_3_values) / len(next_3_values)
        next_3_outlook = _classify_position(avg_next_3, overall_avg)
    else:
        # Fall back to historical averages for next 3 months
        next_avgs = [monthly_avg.get(m, overall_avg) for m in next_months]
        avg_next_3 = sum(next_avgs) / len(next_avgs)
        next_3_outlook = _classify_position(avg_next_3, overall_avg)

    return {
        "peak_month": peak_month_name,
        "peak_month_number": peak_month_num,
        "current_position": current_position,
        "current_month": calendar.month_name[current_month],
        "next_3_months": next_3_outlook,
        "next_months": [calendar.month_name[m] for m in next_months],
        "monthly_averages": {
            calendar.month_name[m]: round(v, 0)
            for m, v in sorted(monthly_avg.items())
        },
    }


def _classify_position(value: float, overall_avg: float) -> str:
    """Classify a value relative to the overall average.

    Returns 'High' if >= 110% of average, 'Low' if <= 90%, otherwise 'Moderate'.
    """
    if overall_avg <= 0:
        return "Moderate"
    ratio = value / overall_avg
    if ratio >= 1.10:
        return "High"
    elif ratio <= 0.90:
        return "Low"
    return "Moderate"
