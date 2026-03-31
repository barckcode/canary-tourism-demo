"""Inter-island province comparison endpoints.

Provides side-by-side tourism indicator data for Santa Cruz de Tenerife
province (ES709) and Las Palmas province (ES701).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    AccommodationComparisonResponse,
    AccommodationTypeData,
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
    "adr": {
        "ES709": "hotel_adr_tenerife",
        "ES701": "hotel_adr_las_palmas",
    },
    "revpar": {
        "ES709": "hotel_revpar_tenerife",
        "ES701": "hotel_revpar_las_palmas",
    },
    "apartamento_ocupacion": {
        "ES709": "apartamento_ocupacion_plazas_tenerife",
        "ES701": "apartamento_ocupacion_plazas_las_palmas",
    },
    "apartamento_estancia_media": {
        "ES709": "apartamento_estancia_media_tenerife",
        "ES701": "apartamento_estancia_media_las_palmas",
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

    - **indicator**: one of viajeros, pernoctaciones, estancia_media, ocupacion_plazas, adr, revpar, apartamento_ocupacion, apartamento_estancia_media
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


# ---------------------------------------------------------------------------
# Accommodation type comparison (rural vs hotel)
# ---------------------------------------------------------------------------

ACCOMMODATION_INDICATORS = {
    "viajeros": {
        "rural": ("rural_viajeros_canarias", "ES70"),
        "hotel": ("hotel_viajeros_tenerife", "ES709"),
    },
    "pernoctaciones": {
        "rural": ("rural_pernoctaciones_canarias", "ES70"),
        "hotel": ("hotel_pernoctaciones_tenerife", "ES709"),
    },
    "plazas": {
        "rural": ("rural_plazas_canarias", "ES70"),
        "hotel": ("hotel_plazas_estimadas_tenerife", "ES709"),
    },
}

ACCOMMODATION_TYPE_NAMES = {
    "rural": "Turismo Rural (Canarias)",
    "hotel": "Hotel (SC Tenerife)",
}

VALID_ACCOMMODATION_INDICATORS = sorted(ACCOMMODATION_INDICATORS.keys())


@router.get("/accommodation-types", response_model=AccommodationComparisonResponse)
@limiter.limit("30/minute")
def get_accommodation_comparison(
    request: Request,
    indicator: str = Query(
        default="pernoctaciones",
        description=(
            f"Indicator to compare. Valid values: "
            f"{', '.join(VALID_ACCOMMODATION_INDICATORS)}"
        ),
    ),
    periods: int = Query(
        default=24,
        ge=1,
        le=120,
        description="Number of most recent monthly periods to return.",
    ),
    db: Session = Depends(get_db),
):
    """Compare rural tourism vs hotel accommodation indicators.

    Returns side-by-side time series data for rural tourism (Canarias, ES70)
    and hotel accommodation (Santa Cruz de Tenerife province, ES709).

    - **indicator**: one of viajeros, pernoctaciones, plazas
    - **periods**: number of most recent months to include (default 24)
    """
    if indicator not in ACCOMMODATION_INDICATORS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid indicator '{indicator}'. "
                f"Valid values: {', '.join(VALID_ACCOMMODATION_INDICATORS)}"
            ),
        )

    indicator_map = ACCOMMODATION_INDICATORS[indicator]
    types_result: dict[str, AccommodationTypeData] = {}

    for accom_type, (indicator_name, geo_code) in indicator_map.items():
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

        types_result[accom_type] = AccommodationTypeData(
            name=ACCOMMODATION_TYPE_NAMES[accom_type],
            data=data_points,
        )

    return AccommodationComparisonResponse(
        indicator=indicator,
        types=types_result,
    )
