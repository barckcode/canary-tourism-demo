"""Dashboard KPI and summary endpoints."""

import calendar
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.schemas import (
    DashboardKPIsResponse,
    DashboardSummaryResponse,
    MapDataResponse,
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

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _latest_value(
    db: Session,
    indicator: str,
    geo_code: str,
    measure: str = "ABSOLUTE",
    period: str | None = None,
) -> TimeSeries | None:
    """Get latest TimeSeries value for given indicator/geo/measure, optionally filtered by period."""
    query = db.query(TimeSeries).filter(
        TimeSeries.indicator == indicator,
        TimeSeries.geo_code == geo_code,
        TimeSeries.measure == measure,
    )
    if period:
        query = query.filter(TimeSeries.period == period)
    return query.order_by(TimeSeries.period.desc()).first()


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


@router.get("/kpis", response_model=DashboardKPIsResponse)
@limiter.limit("60/minute")
def get_kpis(request: Request, db: Session = Depends(get_db)):
    """Return latest KPI values for the dashboard."""
    kpis = {}

    # Latest arrivals
    latest = _latest_value(db, "turistas", "ES709")
    if latest and latest.value is not None:
        kpis["latest_arrivals"] = latest.value
        kpis["latest_period"] = latest.period

        # YoY change — guard against malformed period strings
        if latest.period and len(latest.period) >= 4:
            prev_year_period = f"{int(latest.period[:4]) - 1}{latest.period[4:]}"
            prev = _latest_value(db, "turistas", "ES709", period=prev_year_period)
            if prev is not None and prev.value is not None and prev.value != 0:
                kpis["yoy_change"] = round(
                    (latest.value - prev.value) / prev.value * 100, 2
                )

    # Occupancy rate
    occ = _latest_value(db, "alojatur_habitaciones_ocupacion", "ES709")
    if occ:
        kpis["occupancy_rate"] = occ.value

    # ADR
    adr = _latest_value(db, "alojatur_ingresos_habitacion", "ES709")
    if adr:
        kpis["adr"] = adr.value

    # RevPAR = Revenue Per Available Room (ISTAC: ALOJATUR_REVPAR)
    revpar = _latest_value(db, "alojatur_revpar", "ES709")
    if revpar:
        kpis["revpar"] = revpar.value

    # Average stay
    avg_stay = _latest_value(db, "alojatur_estancias_medias", "ES709")
    if avg_stay:
        kpis["avg_stay"] = avg_stay.value

    # Egatur: average daily spending per tourist (Canarias)
    daily_spend = _latest_value(db, "egatur_gasto_medio_diario_canarias", "ES70")
    if daily_spend and daily_spend.value is not None:
        kpis["daily_spend"] = daily_spend.value
        if daily_spend.period and len(daily_spend.period) >= 4:
            prev_year_period = f"{int(daily_spend.period[:4]) - 1}{daily_spend.period[4:]}"
            prev_ds = _latest_value(
                db, "egatur_gasto_medio_diario_canarias", "ES70", period=prev_year_period
            )
            if prev_ds is not None and prev_ds.value is not None and prev_ds.value != 0:
                kpis["daily_spend_yoy"] = round(
                    (daily_spend.value - prev_ds.value) / prev_ds.value * 100, 2
                )

    # Egatur: average stay duration from INE (Canarias)
    avg_stay_ine = _latest_value(db, "egatur_estancia_media_canarias", "ES70")
    if avg_stay_ine and avg_stay_ine.value is not None:
        kpis["avg_stay_ine"] = avg_stay_ine.value
        if avg_stay_ine.period and len(avg_stay_ine.period) >= 4:
            prev_year_period = f"{int(avg_stay_ine.period[:4]) - 1}{avg_stay_ine.period[4:]}"
            prev_as = _latest_value(
                db, "egatur_estancia_media_canarias", "ES70", period=prev_year_period
            )
            if prev_as is not None and prev_as.value is not None and prev_as.value != 0:
                kpis["avg_stay_ine_yoy"] = round(
                    (avg_stay_ine.value - prev_as.value) / prev_as.value * 100, 2
                )

    # EPA: Total occupied persons in Canarias (thousands)
    emp_total = _latest_value(db, "epa_ocupados_total_canarias", "ES70")
    if emp_total and emp_total.value is not None:
        kpis["employment_total"] = emp_total.value
        if emp_total.period and len(emp_total.period) >= 4:
            prev_year_period = f"{int(emp_total.period[:4]) - 1}{emp_total.period[4:]}"
            prev_et = _latest_value(
                db, "epa_ocupados_total_canarias", "ES70", period=prev_year_period
            )
            if prev_et is not None and prev_et.value is not None and prev_et.value != 0:
                kpis["employment_total_yoy"] = round(
                    (emp_total.value - prev_et.value) / prev_et.value * 100, 2
                )

    # EPA: Occupied persons in services sector in Canarias (thousands)
    emp_services = _latest_value(db, "epa_ocupados_servicios_canarias", "ES70")
    if emp_services and emp_services.value is not None:
        kpis["employment_services"] = emp_services.value
        if emp_services.period and len(emp_services.period) >= 4:
            prev_year_period = f"{int(emp_services.period[:4]) - 1}{emp_services.period[4:]}"
            prev_es = _latest_value(
                db, "epa_ocupados_servicios_canarias", "ES70", period=prev_year_period
            )
            if prev_es is not None and prev_es.value is not None and prev_es.value != 0:
                kpis["employment_services_yoy"] = round(
                    (emp_services.value - prev_es.value) / prev_es.value * 100, 2
                )

    # Hotel Price Index (IPH) - Canarias
    iph_index = _latest_value(db, "iph_indice_canarias", "ES70")
    if iph_index and iph_index.value is not None:
        kpis["iph_index"] = iph_index.value

    iph_var = _latest_value(db, "iph_variacion_canarias", "ES70")
    if iph_var and iph_var.value is not None:
        kpis["iph_variation"] = iph_var.value

    # Last updated
    last_fetched = db.query(func.max(TimeSeries.fetched_at)).scalar()
    kpis["last_updated"] = last_fetched

    if not kpis or "latest_arrivals" not in kpis:
        return {
            "latest_arrivals": None,
            "latest_period": None,
            "yoy_change": None,
            "occupancy_rate": None,
            "adr": None,
            "revpar": None,
            "avg_stay": None,
            "daily_spend": None,
            "daily_spend_yoy": None,
            "avg_stay_ine": None,
            "avg_stay_ine_yoy": None,
            "employment_total": None,
            "employment_total_yoy": None,
            "employment_services": None,
            "employment_services_yoy": None,
            "iph_index": None,
            "iph_variation": None,
            "last_updated": kpis.get("last_updated"),
            "data_available": False,
            "reason": "no_data_available",
        }

    kpis["data_available"] = True
    kpis["reason"] = None
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

    # Occupancy trend (last 24 months)
    occupancy = (
        db.query(TimeSeries.period, TimeSeries.value)
        .filter(
            TimeSeries.indicator == "alojatur_habitaciones_ocupacion",
            TimeSeries.geo_code == "ES709",
            TimeSeries.measure == "ABSOLUTE",
        )
        .order_by(desc(TimeSeries.period))
        .limit(24)
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
        return {
            "arrivals_trend_24m": [],
            "occupancy_trend_12m": [],
            "forecast": [],
            "data_available": False,
            "reason": "no_data_available",
        }

    return {
        "arrivals_trend_24m": arrivals_trend,
        "occupancy_trend_12m": occupancy_trend,
        "forecast": forecast_trend,
        "data_available": True,
        "reason": None,
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
        return {
            "markets": [],
            "total": 0,
            "data_available": False,
            "reason": "no_data_available",
        }

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

    return {"markets": markets, "total": total, "data_available": True, "reason": None}


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

    _empty_seasonal = {
        "peak_month": None,
        "peak_month_number": None,
        "current_position": None,
        "current_month": None,
        "next_3_months": None,
        "next_months": [],
        "monthly_averages": {},
        "data_available": False,
    }

    if not arrivals:
        return {**_empty_seasonal, "reason": "no_data_available"}

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
        return {**_empty_seasonal, "reason": "no_data_available"}

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
        "data_available": True,
        "reason": None,
    }


# ---------------------------------------------------------------------------
# Map data: municipality-level tourism intensity
# ---------------------------------------------------------------------------

# Mapping from INE geo_codes (used in time_series) to municipality codes (GeoJSON)
_GEO_TO_MUNICIPALITY: dict[str, str] = {
    "ES709_ADEJE": "38001",
    "ES709_ARONA": "38006",
    "ES709_PCRUZ": "38028",
}

# Indicator names for hotel pernoctaciones by municipality
_MUNICIPALITY_INDICATORS: dict[str, str] = {
    "ES709_ADEJE": "hotel_pernoctaciones_adeje",
    "ES709_ARONA": "hotel_pernoctaciones_arona",
    "ES709_PCRUZ": "hotel_pernoctaciones_puerto_cruz",
}

# All 12 municipalities in the GeoJSON with their names and zones
_ALL_MUNICIPALITIES: dict[str, dict[str, str]] = {
    "38001": {"name": "Adeje", "zone": "south"},
    "38006": {"name": "Arona", "zone": "south"},
    "38028": {"name": "Puerto de la Cruz", "zone": "north"},
    "38038": {"name": "Santa Cruz de Tenerife", "zone": "metro"},
    "38023": {"name": "San Cristobal de La Laguna", "zone": "metro"},
    "38026": {"name": "La Orotava", "zone": "north"},
    "38017": {"name": "Granadilla de Abona", "zone": "south"},
    "38042": {"name": "Santiago del Teide", "zone": "west"},
    "38019": {"name": "Guia de Isora", "zone": "west"},
    "38020": {"name": "Icod de los Vinos", "zone": "north"},
    "38031": {"name": "Los Realejos", "zone": "north"},
    "38035": {"name": "San Miguel de Abona", "zone": "south"},
}

# Estimation factors for municipalities without direct INE data,
# expressed as a fraction of the max municipality's pernoctaciones.
_ZONE_FACTORS: dict[str, float] = {
    "south": 0.60,
    "north": 0.30,
    "west": 0.40,
    "metro": 0.25,
}

# Hardcoded fallback values when no data is available at all
_FALLBACK_INTENSITIES: dict[str, int] = {
    "38001": 95,   # Adeje
    "38006": 88,   # Arona
    "38028": 65,   # Puerto de la Cruz
    "38038": 23,   # Santa Cruz
    "38023": 20,   # La Laguna
    "38026": 30,   # La Orotava
    "38017": 55,   # Granadilla
    "38042": 40,   # Santiago del Teide
    "38019": 38,   # Guia de Isora
    "38020": 25,   # Icod
    "38031": 28,   # Los Realejos
    "38035": 50,   # San Miguel
}


@router.get("/map", response_model=MapDataResponse)
@limiter.limit("60/minute")
def get_map_data(
    request: Request,
    period: str = Query(
        None,
        description="Period in YYYY-MM format. If omitted, the latest available period is used.",
    ),
    db: Session = Depends(get_db),
):
    """Return municipality-level tourism intensity data for the map.

    Uses real INE hotel pernoctaciones data for Adeje, Arona, and Puerto de la
    Cruz. For municipalities without direct data, intensity is estimated based
    on their geographic zone relative to the maximum observed value.

    When no data exists for the requested period (or the database is empty),
    a hardcoded fallback is returned with ``data_available=false``.
    """
    _validate_period(period, "period")

    # Collect all relevant indicators
    indicator_names = list(_MUNICIPALITY_INDICATORS.values())

    # Determine which period to use
    if period is None:
        # Find the latest available period across all municipality indicators
        latest_row = (
            db.query(TimeSeries.period)
            .filter(
                TimeSeries.indicator.in_(indicator_names),
                TimeSeries.measure == "ABSOLUTE",
                TimeSeries.value.isnot(None),
            )
            .order_by(desc(TimeSeries.period))
            .first()
        )
        if latest_row is None:
            # No data at all -- return fallback
            return _fallback_response()
        period = latest_row.period

    # Query real data for the requested period
    rows = (
        db.query(TimeSeries.indicator, TimeSeries.geo_code, TimeSeries.value)
        .filter(
            TimeSeries.indicator.in_(indicator_names),
            TimeSeries.measure == "ABSOLUTE",
            TimeSeries.period == period,
            TimeSeries.value.isnot(None),
        )
        .all()
    )

    if not rows:
        # No data for this specific period
        return _fallback_response()

    # Build a lookup: municipality_code -> pernoctaciones value
    real_data: dict[str, float] = {}
    for row in rows:
        for geo_code, indicator in _MUNICIPALITY_INDICATORS.items():
            if row.indicator == indicator:
                muni_code = _GEO_TO_MUNICIPALITY[geo_code]
                real_data[muni_code] = row.value
                break

    if not real_data:
        return _fallback_response()

    # Compute max pernoctaciones for normalization
    max_pernoctaciones = max(real_data.values())

    municipalities: dict[str, dict] = {}
    for muni_code, info in _ALL_MUNICIPALITIES.items():
        if muni_code in real_data:
            pernoctaciones = real_data[muni_code]
            if max_pernoctaciones > 0:
                intensity = round(pernoctaciones / max_pernoctaciones * 100)
            else:
                intensity = 0
            municipalities[muni_code] = {
                "name": info["name"],
                "tourism_intensity": min(intensity, 100),
                "pernoctaciones": pernoctaciones,
                "source": "real",
            }
        else:
            # Estimate based on zone
            zone = info["zone"]
            factor = _ZONE_FACTORS.get(zone, 0.25)
            estimated_pernoctaciones = max_pernoctaciones * factor
            intensity = round(factor * 100)
            municipalities[muni_code] = {
                "name": info["name"],
                "tourism_intensity": min(intensity, 100),
                "source": "estimated",
            }

    return {
        "period": period,
        "municipalities": municipalities,
        "data_available": True,
    }


def _fallback_response() -> dict:
    """Return hardcoded fallback data when no real data is available."""
    municipalities = {}
    for muni_code, info in _ALL_MUNICIPALITIES.items():
        municipalities[muni_code] = {
            "name": info["name"],
            "tourism_intensity": _FALLBACK_INTENSITIES.get(muni_code, 25),
            "source": "estimated",
        }
    return {
        "period": None,
        "municipalities": municipalities,
        "data_available": False,
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
