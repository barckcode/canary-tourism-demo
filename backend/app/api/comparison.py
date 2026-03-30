"""Inter-island province comparison endpoints.

Provides side-by-side tourism indicator data for Santa Cruz de Tenerife
province (ES709) and Las Palmas province (ES701).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    ProvinceComparisonResponse,
    ProvinceData,
    ProvinceDataPoint,
)
from app.db.database import get_db
from app.rate_limit import limiter

router = APIRouter()

# Mapping of comparable indicators between provinces
PROVINCE_INDICATORS = {
    "viajeros": {
        "ES709": "hotel_viajeros_tenerife",
        "ES701": "hotel_viajeros_las_palmas",
    },
    "pernoctaciones": {
        "ES709": "hotel_pernoctaciones_tenerife",
        "ES701": "hotel_pernoctaciones_las_palmas",
    },
    "estancia_media": {
        "ES709": "hotel_estancia_media_tenerife",
        "ES701": "hotel_estancia_media_las_palmas",
    },
    "ocupacion_plazas": {
        "ES709": "hotel_ocupacion_plazas_tenerife",
        "ES701": "hotel_ocupacion_plazas_las_palmas",
    },
}

PROVINCE_NAMES = {
    "ES709": "Santa Cruz de Tenerife",
    "ES701": "Las Palmas",
}

VALID_INDICATORS = sorted(PROVINCE_INDICATORS.keys())


@router.get("/provinces", response_model=ProvinceComparisonResponse)
@limiter.limit("30/minute")
def compare_provinces(
    request: Request,
    indicator: str = Query(
        default="pernoctaciones",
        description=f"Indicator to compare. Valid values: {', '.join(VALID_INDICATORS)}",
    ),
    periods: int = Query(
        default=24,
        ge=1,
        le=120,
        description="Number of most recent monthly periods to return.",
    ),
    db: Session = Depends(get_db),
):
    """Compare tourism indicators between the two Canary Islands provinces.

    Returns side-by-side time series data for Santa Cruz de Tenerife (ES709)
    and Las Palmas (ES701) provinces.

    - **indicator**: one of viajeros, pernoctaciones, estancia_media, ocupacion_plazas
    - **periods**: number of most recent months to include (default 24)
    """
    if indicator not in PROVINCE_INDICATORS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid indicator '{indicator}'. "
                f"Valid values: {', '.join(VALID_INDICATORS)}"
            ),
        )

    indicator_map = PROVINCE_INDICATORS[indicator]
    provinces_result: dict[str, ProvinceData] = {}

    for geo_code, indicator_name in indicator_map.items():
        rows = db.execute(
            text(
                "SELECT period, value FROM time_series "
                "WHERE indicator = :indicator AND geo_code = :geo_code "
                "ORDER BY period DESC LIMIT :limit"
            ),
            {"indicator": indicator_name, "geo_code": geo_code, "limit": periods},
        ).fetchall()

        # Reverse to chronological order
        data_points = [
            ProvinceDataPoint(period=row[0], value=row[1])
            for row in reversed(rows)
        ]

        provinces_result[geo_code] = ProvinceData(
            name=PROVINCE_NAMES[geo_code],
            data=data_points,
        )

    return ProvinceComparisonResponse(
        indicator=indicator,
        provinces=provinces_result,
    )
