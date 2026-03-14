"""Data quality validators for ETL pipeline.

Provides schema validation, range checks, completeness checks,
and deduplication logic for time series and microdata records.
"""

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ValidationError:
    """Represents a single validation issue."""

    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error", "warning"

    def __repr__(self) -> str:
        return f"ValidationError({self.severity}: {self.field} - {self.message})"


class ValidationResult:
    """Aggregated result of validation checks."""

    def __init__(self):
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []
        self.records_checked: int = 0
        self.records_valid: int = 0
        self.records_dropped: int = 0
        self.duplicates_removed: int = 0

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, field: str, message: str):
        self.errors.append(ValidationError(field, message, "error"))

    def add_warning(self, field: str, message: str):
        self.warnings.append(ValidationError(field, message, "warning"))

    def summary(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "records_checked": self.records_checked,
            "records_valid": self.records_valid,
            "records_dropped": self.records_dropped,
            "duplicates_removed": self.duplicates_removed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


# Valid period patterns
PERIOD_MONTHLY = re.compile(r"^\d{4}-\d{2}$")          # 2025-03
PERIOD_QUARTERLY = re.compile(r"^\d{4}-Q[1-4]$")       # 2025-Q1
PERIOD_QUARTERLY_ALT = re.compile(r"^\d{4}Q[1-4]$")    # 2025Q1
PERIOD_ANNUAL = re.compile(r"^\d{4}$")                  # 2025

VALID_SOURCES = {"istac", "ine", "cabildo"}
VALID_MEASURES = {"ABSOLUTE", "PERCENTAGE_RATE", "ANNUAL_PERCENTAGE_RATE", "RATE"}


def _is_valid_period(period: str) -> bool:
    """Check if a period string matches a known format."""
    return bool(
        PERIOD_MONTHLY.match(period)
        or PERIOD_QUARTERLY.match(period)
        or PERIOD_QUARTERLY_ALT.match(period)
        or PERIOD_ANNUAL.match(period)
    )


def _is_reasonable_value(value: float, measure: str) -> bool:
    """Check if a value is within reasonable bounds for its measure type."""
    if measure in ("PERCENTAGE_RATE", "ANNUAL_PERCENTAGE_RATE", "RATE"):
        return -100.0 <= value <= 200.0
    # For absolute values, just check non-negative (tourism counts)
    return value >= 0


def validate_timeseries(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """Validate and clean a list of time series records.

    Performs:
    - Schema validation (required fields, correct types)
    - Range checks (valid dates, non-negative values, percentages in range)
    - Deduplication (by source + indicator + geo_code + period + measure)

    Args:
        records: List of record dicts with keys: source, indicator,
            geo_code, period, measure, value.

    Returns:
        Tuple of (valid_records, validation_result).
    """
    result = ValidationResult()
    result.records_checked = len(records)

    valid_records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, ...]] = set()

    for i, rec in enumerate(records):
        is_valid = True

        # Schema validation: required fields
        for field in ("source", "indicator", "geo_code", "period", "measure", "value"):
            if field not in rec or rec[field] is None:
                result.add_error(field, f"Record {i}: missing required field '{field}'")
                is_valid = False

        if not is_valid:
            result.records_dropped += 1
            continue

        # Type validation
        if not isinstance(rec["value"], (int, float)):
            result.add_error("value", f"Record {i}: value must be numeric, got {type(rec['value'])}")
            result.records_dropped += 1
            continue

        # Source validation
        source = str(rec["source"]).lower()
        if source not in VALID_SOURCES:
            result.add_warning("source", f"Record {i}: unknown source '{source}'")

        # Period validation
        period = str(rec["period"])
        if not _is_valid_period(period):
            result.add_warning("period", f"Record {i}: unusual period format '{period}'")

        # Year range check (1990 to now+5 is reasonable for this dataset)
        max_year = datetime.now().year + 5
        year_match = re.match(r"^(\d{4})", period)
        if year_match:
            year = int(year_match.group(1))
            if year < 1990 or year > max_year:
                result.add_error("period", f"Record {i}: year {year} out of range [1990, {max_year}]")
                result.records_dropped += 1
                continue

        # Value range check
        measure = str(rec["measure"])
        value = float(rec["value"])
        if not _is_reasonable_value(value, measure):
            result.add_warning(
                "value",
                f"Record {i}: value {value} may be out of range for measure '{measure}'"
            )

        # Deduplication
        dedup_key = (source, str(rec["indicator"]), str(rec["geo_code"]), period, measure)
        if dedup_key in seen_keys:
            result.duplicates_removed += 1
            continue
        seen_keys.add(dedup_key)

        # Normalize the record
        valid_records.append(
            {
                "source": source,
                "indicator": str(rec["indicator"]).lower(),
                "geo_code": str(rec["geo_code"]),
                "period": period,
                "measure": measure,
                "value": value,
            }
        )

    result.records_valid = len(valid_records)
    result.records_dropped = result.records_checked - result.records_valid - result.duplicates_removed

    if result.errors:
        logger.warning(
            "Time series validation: %d errors, %d warnings, %d/%d records valid.",
            len(result.errors),
            len(result.warnings),
            result.records_valid,
            result.records_checked,
        )
    else:
        logger.info(
            "Time series validation passed: %d/%d records valid, %d duplicates removed.",
            result.records_valid,
            result.records_checked,
            result.duplicates_removed,
        )

    return valid_records, result


def validate_microdata(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ValidationResult]:
    """Validate and clean a list of microdata records.

    Performs:
    - Schema validation (required fields: quarter, cuestionario)
    - Range checks (age 0-120, non-negative spending, nights 0-365)
    - Deduplication (by quarter + cuestionario)

    Args:
        records: List of microdata record dicts.

    Returns:
        Tuple of (valid_records, validation_result).
    """
    result = ValidationResult()
    result.records_checked = len(records)

    valid_records: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()

    for i, rec in enumerate(records):
        is_valid = True

        # Required fields
        if not rec.get("quarter"):
            result.add_error("quarter", f"Record {i}: missing quarter")
            is_valid = False

        cuestionario = rec.get("cuestionario")
        if cuestionario is None:
            result.add_error("cuestionario", f"Record {i}: missing cuestionario")
            is_valid = False

        if not is_valid:
            result.records_dropped += 1
            continue

        # Quarter format check
        quarter = str(rec["quarter"]).upper()
        if not re.match(r"^\d{4}Q[1-4]$", quarter):
            result.add_warning("quarter", f"Record {i}: unusual quarter format '{quarter}'")

        # Age range check
        edad = rec.get("edad")
        if edad is not None and (edad < 0 or edad > 120):
            result.add_warning("edad", f"Record {i}: age {edad} out of range [0, 120]")

        # Spending range checks
        for spend_field in ("gasto_euros", "coste_vuelos_euros", "coste_aloj_euros"):
            val = rec.get(spend_field)
            if val is not None and val < 0:
                result.add_warning(
                    spend_field,
                    f"Record {i}: negative spending {val} in {spend_field}"
                )

        # Nights range check
        noches = rec.get("noches")
        if noches is not None and (noches < 0 or noches > 365):
            result.add_warning("noches", f"Record {i}: nights {noches} out of range [0, 365]")

        # Deduplication
        dedup_key = (quarter, int(cuestionario))
        if dedup_key in seen_keys:
            result.duplicates_removed += 1
            continue
        seen_keys.add(dedup_key)

        valid_records.append(rec)

    result.records_valid = len(valid_records)
    result.records_dropped = result.records_checked - result.records_valid - result.duplicates_removed

    if result.errors:
        logger.warning(
            "Microdata validation: %d errors, %d warnings, %d/%d records valid.",
            len(result.errors),
            len(result.warnings),
            result.records_valid,
            result.records_checked,
        )
    else:
        logger.info(
            "Microdata validation passed: %d/%d records valid, %d duplicates removed.",
            result.records_valid,
            result.records_checked,
            result.duplicates_removed,
        )

    return valid_records, result


def check_completeness(
    records: list[dict[str, Any]],
    indicator: str,
    expected_freq: str = "monthly",
) -> list[str]:
    """Check for gaps in a time series.

    Args:
        records: List of validated time series records.
        indicator: Indicator name to filter by.
        expected_freq: 'monthly' or 'quarterly'.

    Returns:
        List of missing period strings.
    """
    filtered = [
        r["period"] for r in records
        if r.get("indicator") == indicator
        and PERIOD_MONTHLY.match(r["period"])
    ]

    if not filtered:
        return []

    filtered.sort()
    first = filtered[0]
    last = filtered[-1]

    # Generate expected periods
    expected: list[str] = []
    if expected_freq == "monthly":
        year_start, month_start = int(first[:4]), int(first[5:7])
        year_end, month_end = int(last[:4]), int(last[5:7])

        y, m = year_start, month_start
        while (y, m) <= (year_end, month_end):
            expected.append(f"{y}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1
    elif expected_freq == "quarterly":
        # Not implemented for quarterly yet; just return empty
        return []

    present = set(filtered)
    missing = [p for p in expected if p not in present]

    if missing:
        logger.warning(
            "Completeness check for '%s': %d missing periods out of %d expected.",
            indicator,
            len(missing),
            len(expected),
        )

    return missing
