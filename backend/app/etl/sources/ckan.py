"""CKAN API connector.

Fetches EGT microdata packages and Cabildo datasets from CKAN portals
at datos.canarias.es and datos.tenerife.es.
"""

import csv
import io
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# CKAN portals
ISTAC_CKAN_URL = "https://datos.canarias.es/catalogos/estadisticas"
CABILDO_CKAN_URL = "https://datos.tenerife.es"

# Known CKAN package names for EGT microdata
EGT_PACKAGE_NAMES = [
    "encuesta-sobre-gasto-turistico",
    "encuesta-gasto-turistico-microdatos",
]

# Placeholder codes used in EGT microdata
PLACEHOLDER_CODES = {"_Z", "_U", "_N", "_Y", ""}


def _safe_int(val: str) -> int | None:
    """Safely convert string to int, returning None for placeholders."""
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val: str) -> float | None:
    """Safely convert string to float, returning None for placeholders."""
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def _ckan_package_show(
    client: httpx.AsyncClient, base_url: str, package_name: str
) -> dict[str, Any] | None:
    """Fetch CKAN package metadata."""
    url = f"{base_url}/api/3/action/package_show"
    params = {"id": package_name}
    try:
        resp = await client.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        result = resp.json()
        if result.get("success"):
            return result.get("result")
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "CKAN package_show failed for %s: HTTP %d",
            package_name,
            exc.response.status_code,
        )
        return None
    except httpx.RequestError as exc:
        logger.error("CKAN request error for %s: %s", package_name, exc)
        return None


async def _ckan_package_search(
    client: httpx.AsyncClient,
    base_url: str,
    query: str,
    rows: int = 10,
) -> list[dict[str, Any]]:
    """Search CKAN packages by query string."""
    url = f"{base_url}/api/3/action/package_search"
    params = {"q": query, "rows": rows}
    try:
        resp = await client.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        result = resp.json()
        if result.get("success"):
            return result.get("result", {}).get("results", [])
        return []
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("CKAN search error: %s", exc)
        return []


async def _download_csv_resource(
    client: httpx.AsyncClient, url: str, encoding: str = "latin-1"
) -> list[dict[str, str]]:
    """Download and parse a CSV resource from CKAN."""
    try:
        resp = await client.get(url, timeout=120.0, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content.decode(encoding, errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        return list(reader)
    except httpx.HTTPStatusError as exc:
        logger.warning("CSV download failed for %s: HTTP %d", url, exc.response.status_code)
        return []
    except httpx.RequestError as exc:
        logger.error("CSV download error for %s: %s", url, exc)
        return []
    except Exception as exc:
        logger.error("CSV parse error for %s: %s", url, exc)
        return []


def _parse_microdata_row(row: dict[str, str], quarter: str) -> dict[str, Any] | None:
    """Parse a single EGT microdata row into a microdata-compatible record.

    Filters to Tenerife (ES709) and extracts key fields.
    """
    isla = row.get("ISLA", "")
    if isla != "ES709":
        return None

    cuestionario = _safe_int(row.get("NUMERO_CUESTIONARIO", ""))
    if cuestionario is None:
        return None

    record: dict[str, Any] = {
        "quarter": quarter,
        "cuestionario": cuestionario,
        "isla": row.get("ISLA") or None,
        "aeropuerto": row.get("AEROPUERTO_ORIGEN") or None,
        "sexo": row.get("SEXO") or None,
        "edad": _safe_int(row.get("EDAD", "")),
        "nacionalidad": row.get("NACIONALIDAD") or None,
        "pais_residencia": row.get("PAIS_RESIDENCIA") or None,
        "proposito": row.get("PROPOSITO") or None,
        "noches": _safe_int(row.get("NOCHES", "")),
        "aloj_categ": row.get("ALOJ_CATEG") or None,
        "gasto_euros": _safe_float(row.get("GASTO_EUROS", "")),
        "coste_vuelos_euros": _safe_float(row.get("COSTE_VUELOS_EUROS", "")),
        "coste_aloj_euros": _safe_float(row.get("COSTE_ALOJ_EUROS", "")),
        "satisfaccion": row.get("SATISFACCION") or None,
        "raw_json": json.dumps(
            {k: v for k, v in row.items() if v not in PLACEHOLDER_CODES},
            ensure_ascii=False,
        ),
    }

    # Clean placeholder values in string fields
    for key in [
        "isla", "aeropuerto", "sexo", "nacionalidad",
        "pais_residencia", "proposito", "aloj_categ", "satisfaccion",
    ]:
        if record[key] in PLACEHOLDER_CODES:
            record[key] = None

    return record


def _extract_quarter_from_resource(resource: dict[str, Any]) -> str | None:
    """Try to extract quarter information from a CKAN resource name/description.

    Expected patterns: '2024Q3', '2024-Q3', 'T3 2024', '3er trimestre 2024'
    """
    import re

    name = resource.get("name", "") + " " + resource.get("description", "")
    name = name.upper()

    # Pattern: 2024Q3 or 2024-Q3
    match = re.search(r"(\d{4})[_\-]?Q(\d)", name)
    if match:
        return f"{match.group(1)}Q{match.group(2)}"

    # Pattern: T3 2024 or T3_2024
    match = re.search(r"T(\d)[_\s]*(\d{4})", name)
    if match:
        return f"{match.group(2)}Q{match.group(1)}"

    # Pattern: trimestre
    match = re.search(r"(\d)\w*\s*TRIMESTRE\s*(\d{4})", name)
    if match:
        return f"{match.group(2)}Q{match.group(1)}"

    return None


async def check_for_updates(
    last_known_modified: dict[str, str] | None = None,
) -> dict[str, str]:
    """Check if CKAN packages have new data based on metadata_modified.

    Args:
        last_known_modified: Dict mapping package name to last known
            metadata_modified timestamp.

    Returns:
        Dict of package names with new data, mapped to their
        metadata_modified timestamp.
    """
    if last_known_modified is None:
        last_known_modified = {}

    updated: dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        for package_name in EGT_PACKAGE_NAMES:
            pkg = await _ckan_package_show(client, ISTAC_CKAN_URL, package_name)
            if pkg is None:
                continue

            modified = pkg.get("metadata_modified", "")
            if modified and modified != last_known_modified.get(package_name):
                updated[package_name] = modified

    return updated


async def fetch_egt_microdata(
    package_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch and parse EGT microdata CSV resources from CKAN.

    Args:
        package_names: List of CKAN package names to fetch. If None,
            uses default EGT package names.

    Returns:
        List of microdata-compatible record dicts (filtered to Tenerife).
    """
    names = package_names or EGT_PACKAGE_NAMES
    all_records: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for package_name in names:
            logger.info("Fetching CKAN package: %s", package_name)
            pkg = await _ckan_package_show(client, ISTAC_CKAN_URL, package_name)
            if pkg is None:
                continue

            resources = pkg.get("resources", [])
            csv_resources = [
                r for r in resources
                if r.get("format", "").upper() == "CSV"
                or r.get("url", "").lower().endswith(".csv")
            ]

            for resource in csv_resources:
                url = resource.get("url", "")
                if not url:
                    continue

                quarter = _extract_quarter_from_resource(resource)
                if quarter is None:
                    # Try extracting from URL
                    import re
                    match = re.search(r"(\d{4})[_\-]?[qQ](\d)", url)
                    if match:
                        quarter = f"{match.group(1)}Q{match.group(2)}"
                    else:
                        logger.warning(
                            "Could not determine quarter for resource: %s",
                            resource.get("name", url),
                        )
                        continue

                logger.info(
                    "Downloading CSV resource: %s (quarter=%s)",
                    resource.get("name", url),
                    quarter,
                )
                rows = await _download_csv_resource(client, url)

                for row in rows:
                    record = _parse_microdata_row(row, quarter)
                    if record is not None:
                        all_records.append(record)

                logger.info(
                    "CKAN %s/%s: parsed %d Tenerife records from %d rows.",
                    package_name,
                    quarter,
                    sum(1 for _ in []),  # placeholder
                    len(rows),
                )

    logger.info("CKAN fetch complete: %d total microdata records.", len(all_records))
    return all_records


async def fetch_cabildo_datasets() -> list[dict[str, Any]]:
    """Fetch datasets from Cabildo de Tenerife CKAN portal.

    Note: datos.tenerife.es is frequently offline. This connector
    handles that gracefully by returning empty results on failure.

    Returns:
        List of TimeSeries-compatible record dicts.
    """
    all_records: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        # Search for tourism-related datasets
        packages = await _ckan_package_search(
            client, CABILDO_CKAN_URL, "turismo", rows=20
        )

        if not packages:
            logger.warning(
                "No Cabildo datasets found (portal may be offline)."
            )
            return all_records

        for pkg in packages:
            pkg_name = pkg.get("name", "unknown")
            resources = pkg.get("resources", [])

            for resource in resources:
                fmt = resource.get("format", "").upper()
                url = resource.get("url", "")

                if fmt == "CSV" and url:
                    logger.info("Downloading Cabildo CSV: %s", url)
                    rows = await _download_csv_resource(
                        client, url, encoding="utf-8"
                    )

                    for row in rows:
                        # Try to parse as time series if it has the right columns
                        value = _safe_float(
                            row.get("OBS_VALUE", row.get("value", ""))
                        )
                        period = row.get(
                            "TIME_PERIOD_CODE",
                            row.get("period", row.get("time", "")),
                        )
                        if value is not None and period:
                            all_records.append(
                                {
                                    "source": "cabildo",
                                    "indicator": pkg_name,
                                    "geo_code": row.get(
                                        "TERRITORIO_CODE",
                                        row.get("geo_code", "ES709"),
                                    ),
                                    "period": period,
                                    "measure": row.get(
                                        "MEDIDAS_CODE",
                                        row.get("measure", "ABSOLUTE"),
                                    ),
                                    "value": value,
                                }
                            )

    logger.info("Cabildo fetch complete: %d records.", len(all_records))
    return all_records
