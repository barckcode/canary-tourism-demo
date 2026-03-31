"""ISTAC API connector.

Fetches tourism indicators (FRONTUR arrivals, accommodation metrics)
from the ISTAC REST API at datos.canarias.es.
"""

import logging
from typing import Any

import httpx

from app.etl.retry import async_fetch_with_retry

logger = logging.getLogger(__name__)

BASE_URL = "https://datos.canarias.es/api/estadisticas/indicators/v1.0"

# ISTAC indicator codes relevant to Tenerife tourism
INDICATOR_CODES = [
    "TURISTAS",
    "TURISTAS_EXTRANJEROS",
    "TURISTAS_NACIONALES",
    "ALOJATUR_OCUPACION",
    "ALOJATUR_OCUPACION_PLAZAS",
    "ALOJATUR_ADR",
    "ALOJATUR_REVPAR",
    "ALOJATUR_PERNOCTACIONES",
    "ALOJATUR_ESTANCIA_MEDIA",
    "ALOJATUR_PLAZAS",
    "ALOJATUR_ESTABLECIMIENTOS",
    "ALOJATUR_HABITACIONES",
    "ALOJATUR_PERSONAL",
    "ALOJATUR_INGRESOS",
]

# Tenerife geographic code
TENERIFE_GEO = "ES709"


async def _fetch_indicator_metadata(
    client: httpx.AsyncClient, code: str
) -> dict[str, Any] | None:
    """Fetch indicator metadata including lastUpdate timestamp."""
    url = f"{BASE_URL}/indicators/{code}"
    try:
        resp = await async_fetch_with_retry(
            client, url, timeout=30.0, source_name="ISTAC",
        )
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ISTAC metadata fetch failed for %s: HTTP %d", code, exc.response.status_code
        )
        return None
    except httpx.RequestError as exc:
        logger.error("ISTAC request error for %s: %s", code, exc)
        return None


async def _fetch_indicator_data(
    client: httpx.AsyncClient, code: str
) -> dict[str, Any] | None:
    """Fetch indicator observation data filtered to Tenerife."""
    url = f"{BASE_URL}/indicators/{code}/data"
    params = {
        "representation": f"GEOGRAPHICAL[{TENERIFE_GEO}]",
        "granularity": "MONTHLY",
    }
    try:
        resp = await async_fetch_with_retry(
            client, url, params=params, timeout=60.0, source_name="ISTAC",
        )
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ISTAC data fetch failed for %s: HTTP %d", code, exc.response.status_code
        )
        return None
    except httpx.RequestError as exc:
        logger.error("ISTAC data request error for %s: %s", code, exc)
        return None


def _extract_dimension_codes(
    dim_values: Any, default_id: str = ""
) -> dict[int, str]:
    """Build an {index: code} mapping from ISTAC dimension values.

    Handles both the ``{"value": [...]}`` dict form and the plain list form
    that the ISTAC API may return.
    """
    if isinstance(dim_values, list):
        return {idx: entry.get("id", default_id) for idx, entry in enumerate(dim_values)}
    if isinstance(dim_values, dict):
        entries = dim_values.get("value", [])
        result: dict[int, str] = {}
        for idx, entry in enumerate(entries):
            key = entry.get("order", idx)
            value = entry.get("id", default_id)
            if key in result:
                logger.warning(
                    "ISTAC parser: duplicate key %s (old=%s, new=%s)",
                    key, result[key], value,
                )
            result[key] = value
        return result
    return {}


def _parse_list_observations(
    observations: list,
    indicator_code: str,
    time_codes: dict[int, str],
    geo_codes: dict[int, str],
    measure_codes: dict[int, str],
) -> list[dict[str, Any]]:
    """Parse observations when they arrive as a list of dicts."""
    records: list[dict[str, Any]] = []
    for obs in observations:
        time_idx = obs.get("timeIndex", obs.get("dimensionCodes", {}).get("TIME"))
        geo_idx = obs.get("geographicalIndex", 0)
        measure_idx = obs.get("measureIndex", 0)

        period = time_codes.get(time_idx, "")
        geo_code = geo_codes.get(geo_idx, TENERIFE_GEO)
        measure = measure_codes.get(measure_idx, "ABSOLUTE")

        value = obs.get("value")
        if value is None:
            primary = obs.get("primaryMeasure")
            if primary is not None:
                value = primary

        if value is not None and period:
            records.append({
                "source": "istac",
                "indicator": indicator_code.lower(),
                "geo_code": geo_code,
                "period": period,
                "measure": measure,
                "value": float(value),
            })
    return records


def _parse_dict_observations(
    observations: dict,
    indicator_code: str,
    time_codes: dict[int, str],
    geo_codes: dict[int, str],
    measure_codes: dict[int, str],
) -> list[dict[str, Any]]:
    """Parse observations when they arrive as a dict keyed by composite index."""
    records: list[dict[str, Any]] = []
    for key, value in observations.items():
        if value is None:
            continue
        parts = str(key).split("|")
        time_idx = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        geo_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        measure_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        period = time_codes.get(time_idx, "")
        geo_code = geo_codes.get(geo_idx, TENERIFE_GEO)
        measure = measure_codes.get(measure_idx, "ABSOLUTE")

        obs_value = value if isinstance(value, (int, float)) else None
        if isinstance(value, dict):
            obs_value = value.get("value")

        if obs_value is not None and period:
            records.append({
                "source": "istac",
                "indicator": indicator_code.lower(),
                "geo_code": geo_code,
                "period": period,
                "measure": measure,
                "value": float(obs_value),
            })
    return records


def _parse_observations(
    data: dict[str, Any], indicator_code: str
) -> list[dict[str, Any]]:
    """Parse ISTAC JSON response into flat TimeSeries-compatible records.

    The ISTAC API returns observations in a nested format with dimension
    indices mapping to codes. We flatten this into records with source,
    indicator, geo_code, period, measure, and value fields.
    """
    dimensions = data.get("dimension", {})

    time_dim = dimensions.get("TIME", dimensions.get("time", {}))
    time_codes = _extract_dimension_codes(time_dim.get("dimensionValues", {}))

    geo_dim = dimensions.get("GEOGRAPHICAL", dimensions.get("geographical", {}))
    geo_codes = _extract_dimension_codes(
        geo_dim.get("dimensionValues", {}), default_id=TENERIFE_GEO
    )

    measure_dim = dimensions.get("MEASURE", dimensions.get("measure", {}))
    measure_codes = _extract_dimension_codes(
        measure_dim.get("dimensionValues", {}), default_id="ABSOLUTE"
    )

    observations = data.get("observation", [])
    if isinstance(observations, list):
        return _parse_list_observations(
            observations, indicator_code, time_codes, geo_codes, measure_codes
        )
    if isinstance(observations, dict):
        return _parse_dict_observations(
            observations, indicator_code, time_codes, geo_codes, measure_codes
        )
    return []


def get_last_update(metadata: dict[str, Any]) -> str | None:
    """Extract the lastUpdate timestamp from indicator metadata."""
    return metadata.get("lastUpdate") or metadata.get("lastUpdated")


async def check_for_updates(
    last_known_updates: dict[str, str] | None = None,
) -> dict[str, str]:
    """Check which indicators have new data since last known update.

    Args:
        last_known_updates: Dict mapping indicator code to last known
            lastUpdate timestamp string.

    Returns:
        Dict of indicator codes that have new data mapped to their
        new lastUpdate timestamp.
    """
    if last_known_updates is None:
        last_known_updates = {}

    updated: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        for code in INDICATOR_CODES:
            metadata = await _fetch_indicator_metadata(client, code)
            if metadata is None:
                continue

            last_update = get_last_update(metadata)
            if last_update and last_update != last_known_updates.get(code):
                updated[code] = last_update

    return updated


async def fetch_indicators(
    indicator_codes: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch ISTAC indicator data for specified codes.

    Args:
        indicator_codes: List of indicator codes to fetch. If None,
            fetches all configured indicators.

    Returns:
        List of TimeSeries-compatible record dicts.
    """
    codes = indicator_codes or INDICATOR_CODES
    all_records: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for code in codes:
            logger.info("Fetching ISTAC indicator: %s", code)
            data = await _fetch_indicator_data(client, code)
            if data is None:
                continue

            records = _parse_observations(data, code)
            logger.info(
                "ISTAC %s: parsed %d observations.", code, len(records)
            )
            all_records.extend(records)

    logger.info("ISTAC fetch complete: %d total records.", len(all_records))
    return all_records
