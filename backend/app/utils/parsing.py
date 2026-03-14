"""Shared parsing utilities for data ingestion.

Used by seed.py, ckan.py, and ine.py to avoid code duplication.
"""

# Placeholder codes used in EGT/ISTAC microdata
PLACEHOLDER_CODES = {"_Z", "_U", "_N", "_Y", ""}

# INE FK_Periodo -> month number (monthly series)
INE_MONTHLY_PERIOD = {i: i for i in range(1, 13)}

# INE FK_Periodo -> quarter label (quarterly series)
INE_QUARTERLY_PERIOD = {19: "Q1", 20: "Q2", 21: "Q3", 22: "Q4"}


def safe_int(val: str) -> int | None:
    """Safely convert string to int, returning None for placeholders."""
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_float(val: str) -> float | None:
    """Safely convert string to float, returning None for placeholders."""
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
