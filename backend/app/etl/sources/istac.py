"""ISTAC API connector.

Fetches tourism indicators (FRONTUR arrivals, accommodation metrics)
from the ISTAC REST API at datos.canarias.es.
"""

import logging
from typing import Any

import httpx

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
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
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
        resp = await client.get(url, params=params, timeout=60.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ISTAC data fetch failed for %s: HTTP %d", code, exc.response.status_code
        )
        return None
    except httpx.RequestError as exc:
        logger.error("ISTAC data request error for %s: %s", code, exc)
        return None


def _parse_observations(
    data: dict[str, Any], indicator_code: str
) -> list[dict[str, Any]]:
    """Parse ISTAC JSON response into flat TimeSeries-compatible records.

    The ISTAC API returns observations in a nested format with dimension
    indices mapping to codes. We flatten this into records with source,
    indicator, geo_code, period, measure, and value fields.
    """
    records: list[dict[str, Any]] = []

    # Extract dimension values for lookup
    dimensions = data.get("dimension", {})

    # Time dimension values
    time_dim = dimensions.get("TIME", dimensions.get("time", {}))
    time_values = time_dim.get("dimensionValues", {})
    time_codes = {
        entry.get("order", idx): entry.get("id", "")
        for idx, entry in enumerate(
            time_values.get("value", []) if isinstance(time_values, dict) else []
        )
    }
    # If time_values is a list directly
    if isinstance(time_values, list):
        time_codes = {
            idx: entry.get("id", "") for idx, entry in enumerate(time_values)
        }

    # Geographic dimension values
    geo_dim = dimensions.get("GEOGRAPHICAL", dimensions.get("geographical", {}))
    geo_values = geo_dim.get("dimensionValues", {})
    geo_list = (
        geo_values.get("value", []) if isinstance(geo_values, dict) else []
    )
    if isinstance(geo_values, list):
        geo_list = geo_values
    geo_codes = {
        idx: entry.get("id", TENERIFE_GEO) for idx, entry in enumerate(geo_list)
    }

    # Measure dimension values
    measure_dim = dimensions.get("MEASURE", dimensions.get("measure", {}))
    measure_values = measure_dim.get("dimensionValues", {})
    measure_list = (
        measure_values.get("value", []) if isinstance(measure_values, dict) else []
    )
    if isinstance(measure_values, list):
        measure_list = measure_values
    measure_codes = {
        idx: entry.get("id", "ABSOLUTE") for idx, entry in enumerate(measure_list)
    }

    # Parse observations
    observations = data.get("observation", [])
    if isinstance(observations, list):
        for obs in observations:
            time_idx = obs.get("timeIndex", obs.get("dimensionCodes", {}).get("TIME"))
            geo_idx = obs.get("geographicalIndex", 0)
            measure_idx = obs.get("measureIndex", 0)

            period = time_codes.get(time_idx, "")
            geo_code = geo_codes.get(geo_idx, TENERIFE_GEO)
            measure = measure_codes.get(measure_idx, "ABSOLUTE")

            value = obs.get("value")
            if value is None:
                # Try primary/secondary value fields
                primary = obs.get("primaryMeasure")
                if primary is not None:
                    value = primary

            if value is not None and period:
                records.append(
                    {
                        "source": "istac",
                        "indicator": indicator_code.lower(),
                        "geo_code": geo_code,
                        "period": period,
                        "measure": measure,
                        "value": float(value),
                    }
                )
    elif isinstance(observations, dict):
        # Some endpoints return observations as a dict keyed by composite index
        for key, value in observations.items():
            if value is None:
                continue
            # Key format can be "time_idx|geo_idx|measure_idx" or similar
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
                records.append(
                    {
                        "source": "istac",
                        "indicator": indicator_code.lower(),
                        "geo_code": geo_code,
                        "period": period,
                        "measure": measure,
                        "value": float(obs_value),
                    }
                )

    return records


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
