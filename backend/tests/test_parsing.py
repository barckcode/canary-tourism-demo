"""Tests for shared parsing utilities in app.utils.parsing."""

from app.utils.parsing import (
    PLACEHOLDER_CODES,
    INE_MONTHLY_PERIOD,
    INE_QUARTERLY_PERIOD,
    safe_float,
    safe_int,
)


# --- safe_int ---

def test_safe_int_valid():
    assert safe_int("42") == 42
    assert safe_int("3.9") == 3  # truncates via int(float(...))


def test_safe_int_placeholder_codes():
    for code in PLACEHOLDER_CODES:
        assert safe_int(code) is None


def test_safe_int_invalid():
    assert safe_int("abc") is None
    assert safe_int("") is None


# --- safe_float ---

def test_safe_float_valid():
    assert safe_float("3.14") == 3.14
    assert safe_float("100") == 100.0


def test_safe_float_placeholder_codes():
    for code in PLACEHOLDER_CODES:
        assert safe_float(code) is None


def test_safe_float_invalid():
    assert safe_float("abc") is None
    assert safe_float("") is None


# --- Period mappings ---

def test_ine_monthly_period_has_12_months():
    assert len(INE_MONTHLY_PERIOD) == 12
    for m in range(1, 13):
        assert m in INE_MONTHLY_PERIOD


def test_ine_quarterly_period_has_4_quarters():
    assert len(INE_QUARTERLY_PERIOD) == 4
    assert INE_QUARTERLY_PERIOD[19] == "Q1"
    assert INE_QUARTERLY_PERIOD[22] == "Q4"


# --- Import compatibility ---

def test_seed_imports_from_utils():
    """Verify seed.py can access utils via its aliases."""
    from app.db.seed import _safe_int, _safe_float, PLACEHOLDER_CODES as PC
    assert _safe_int("5") == 5
    assert _safe_float("2.5") == 2.5
    assert "_Z" in PC


def test_ckan_imports_from_utils():
    """Verify ckan.py can access utils via its aliases."""
    from app.etl.sources.ckan import _safe_int, _safe_float, PLACEHOLDER_CODES as PC
    assert _safe_int("5") == 5
    assert _safe_float("2.5") == 2.5
    assert "_Z" in PC


def test_ine_imports_from_utils():
    """Verify ine.py can access period mappings."""
    from app.etl.sources.ine import INE_MONTHLY_PERIOD as MP, INE_QUARTERLY_PERIOD as QP
    assert len(MP) == 12
    assert len(QP) == 4
