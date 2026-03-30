"""INE API connector.

Fetches hotel occupancy, apartment, rural tourism, resident tourism,
Frontur (international arrivals), and Egatur (tourist spending) series
from the INE REST API at servicios.ine.es.
"""

import logging
from typing import Any

import httpx

from app.etl.retry import async_fetch_with_retry
from app.utils.parsing import INE_MONTHLY_PERIOD, INE_QUARTERLY_PERIOD  # noqa: F401

logger = logging.getLogger(__name__)

BASE_URL = "https://servicios.ine.es/wstempus/js/ES"

# INE series IDs for Tenerife / Canarias tourism data
# Format: (series_id, description, geo_scope)
INE_SERIES = [
    # Hotel occupancy - SC Tenerife province
    ("EOH3949", "hotel_viajeros_tenerife", "ES709"),
    ("EOH3950", "hotel_pernoctaciones_tenerife", "ES709"),
    ("EOH3951", "hotel_estancia_media_tenerife", "ES709"),
    ("EOH3952", "hotel_ocupacion_habitaciones_tenerife", "ES709"),
    ("EOH3953", "hotel_ocupacion_plazas_tenerife", "ES709"),
    ("EOH3954", "hotel_plazas_estimadas_tenerife", "ES709"),
    # Hotel occupancy - Tourist points
    ("EOH12808", "hotel_viajeros_adeje", "ES709_ADEJE"),
    ("EOH12809", "hotel_pernoctaciones_adeje", "ES709_ADEJE"),
    ("EOH12810", "hotel_viajeros_arona", "ES709_ARONA"),
    ("EOH12811", "hotel_pernoctaciones_arona", "ES709_ARONA"),
    ("EOH12812", "hotel_viajeros_puerto_cruz", "ES709_PCRUZ"),
    ("EOH12813", "hotel_pernoctaciones_puerto_cruz", "ES709_PCRUZ"),
    # Tourist apartments - SC Tenerife province
    ("EAT3930", "apartamento_viajeros_tenerife", "ES709"),
    ("EAT3931", "apartamento_pernoctaciones_tenerife", "ES709"),
    ("EAT3932", "apartamento_ocupacion_plazas_tenerife", "ES709"),
    ("EAT3933", "apartamento_plazas_estimadas_tenerife", "ES709"),
    # Rural tourism - Canarias
    ("ETR1208", "rural_viajeros_canarias", "ES70"),
    ("ETR1209", "rural_pernoctaciones_canarias", "ES70"),
    ("ETR1210", "rural_plazas_canarias", "ES70"),
    # Resident tourism - Canarias as destination
    ("ETR_RES240", "residente_viajes_canarias", "ES70"),
    ("ETR_RES241", "residente_pernoctaciones_canarias", "ES70"),
    ("ETR_RES242", "residente_gasto_medio_canarias", "ES70"),
    # Frontur - International tourist arrivals to Canarias
    ("FREG349", "frontur_turistas_canarias", "ES70"),
    # Egatur - Tourist spending in Canarias
    ("FREG531", "egatur_gasto_total_canarias", "ES70"),
    ("FREG529", "egatur_gasto_medio_diario_canarias", "ES70"),
    ("FREG803", "egatur_estancia_media_canarias", "ES70"),
    # EPA - Employment in Canarias (quarterly, thousands of persons)
    ("EPA440086", "epa_ocupados_total_canarias", "ES70"),
    ("EPA440090", "epa_ocupados_servicios_canarias", "ES70"),
]


def _normalize_series_response(data: Any) -> list[dict[str, Any]]:
    """Normalize INE series response into a flat list of records.

    The INE API returns two formats depending on the series:
    - Flat list: ``[{Anyo, FK_Periodo, Valor, ...}, ...]``
    - Wrapper dict: ``{COD, Nombre, Data: [{Anyo, FK_Periodo, Valor, ...}, ...]}``

    This function detects the format and always returns the inner list.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "Data" in data:
        inner = data["Data"]
        if isinstance(inner, list):
            return inner
    return []


async def _fetch_series_data(
    client: httpx.AsyncClient, series_id: str
) -> list[dict[str, Any]] | None:
    """Fetch full data for an INE series."""
    url = f"{BASE_URL}/DATOS_SERIE/{series_id}"
    try:
        resp = await async_fetch_with_retry(
            client, url, timeout=60.0, source_name="INE",
        )
        raw = resp.json()
        records = _normalize_series_response(raw)
        if not records:
            logger.warning("INE %s: empty or unrecognised response format.", series_id)
            return None
        return records
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "INE fetch failed for %s: HTTP %d", series_id, exc.response.status_code
        )
        return None
    except httpx.RequestError as exc:
        logger.error("INE request error for %s: %s", series_id, exc)
        return None


async def _fetch_latest_period(
    client: httpx.AsyncClient, series_id: str
) -> dict[str, Any] | None:
    """Check the latest available period for a series using ?nult=1."""
    url = f"{BASE_URL}/DATOS_SERIE/{series_id}"
    params = {"nult": 1}
    try:
        resp = await async_fetch_with_retry(
            client, url, params=params, timeout=30.0, source_name="INE",
        )
        raw = resp.json()
        records = _normalize_series_response(raw)
        if records:
            return records[0]
        return None
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("INE latest period check failed for %s: %s", series_id, exc)
        return None


def _parse_period(record: dict[str, Any]) -> str | None:
    """Convert INE Anyo + FK_Periodo into a period string.

    Returns formats like '2025-03' for monthly or '2025-Q1' for quarterly.
    """
    anyo = record.get("Anyo")
    fk_periodo = record.get("FK_Periodo")

    if anyo is None or fk_periodo is None:
        return None

    if fk_periodo in INE_QUARTERLY_PERIOD:
        return f"{anyo}-{INE_QUARTERLY_PERIOD[fk_periodo]}"
    elif 1 <= fk_periodo <= 12:
        return f"{anyo}-{fk_periodo:02d}"

    return None


def _parse_series_records(
    data: list[dict[str, Any]], indicator: str, geo_code: str
) -> list[dict[str, Any]]:
    """Parse INE JSON array into TimeSeries-compatible records."""
    records: list[dict[str, Any]] = []

    for rec in data:
        valor = rec.get("Valor")
        if valor is None:
            continue

        period = _parse_period(rec)
        if period is None:
            continue

        records.append(
            {
                "source": "ine",
                "indicator": indicator,
                "geo_code": geo_code,
                "period": period,
                "measure": "ABSOLUTE",
                "value": float(valor),
            }
        )

    return records


async def check_for_updates(
    last_known_periods: dict[str, str] | None = None,
) -> dict[str, str]:
    """Check which INE series have new data.

    Args:
        last_known_periods: Dict mapping series_id to last known period string.

    Returns:
        Dict of series IDs that have new data, mapped to their latest period.
    """
    if last_known_periods is None:
        last_known_periods = {}

    updated: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        for series_id, indicator, geo_code in INE_SERIES:
            latest = await _fetch_latest_period(client, series_id)
            if latest is None:
                continue

            period = _parse_period(latest)
            if period and period != last_known_periods.get(series_id):
                updated[series_id] = period

    return updated


async def fetch_series(
    series_list: list[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Fetch INE series data.

    Args:
        series_list: List of (series_id, indicator_name, geo_code) tuples.
            If None, fetches all configured series.

    Returns:
        List of TimeSeries-compatible record dicts.
    """
    targets = series_list or INE_SERIES
    all_records: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for series_id, indicator, geo_code in targets:
            logger.info("Fetching INE series: %s (%s)", series_id, indicator)
            data = await _fetch_series_data(client, series_id)
            if data is None:
                continue

            records = _parse_series_records(data, indicator, geo_code)
            logger.info(
                "INE %s: parsed %d records.", series_id, len(records)
            )
            all_records.extend(records)

    logger.info("INE fetch complete: %d total records.", len(all_records))
    return all_records
