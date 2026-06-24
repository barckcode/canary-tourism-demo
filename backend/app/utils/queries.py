"""Shared database query helpers used by multiple model modules.

Extracts common data-loading patterns so that trainer.py and
scenario_engine.py (and future modules) use the same logic.
"""

import re

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


def load_arrivals_series(
    db: Session,
    indicator: str = "turistas",
    geo_code: str = "ES709",
) -> pd.Series:
    """Load monthly time series from DB as a pandas Series with PeriodIndex.

    Queries the time_series table for the given indicator and geo_code,
    filtering to monthly (YYYY-MM) periods only.

    Args:
        db: Active SQLAlchemy session.
        indicator: Indicator name (default 'turistas' for backward compatibility).
        geo_code: Geographic code (default 'ES709' for Tenerife).

    Returns:
        A pandas Series with PeriodIndex (freq='M') and float values,
        named after the indicator.
    """
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator=:indicator AND geo_code=:geo_code AND measure='ABSOLUTE'
            ORDER BY period
        """),
        {"indicator": indicator, "geo_code": geo_code},
    ).fetchall()

    # Filter only YYYY-MM format (exclude annual totals)
    monthly = [(r.period, r.value) for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)]

    periods = pd.PeriodIndex([p for p, _ in monthly], freq="M")
    values = np.array([v for _, v in monthly], dtype=float)

    return pd.Series(values, index=periods, name=indicator)


def get_forecastable_indicators(db: Session, geo_code: str = "ES709", min_observations: int = 36) -> list[str]:
    """Return indicator names that have enough monthly data for forecasting.

    Args:
        db: Active SQLAlchemy session.
        geo_code: Geographic code to filter by.
        min_observations: Minimum number of monthly observations required.

    Returns:
        List of indicator names with at least min_observations monthly data points.
    """
    rows = db.execute(
        text("""
            SELECT indicator, COUNT(*) as cnt
            FROM time_series
            WHERE geo_code=:geo_code AND measure='ABSOLUTE'
              AND period GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'
            GROUP BY indicator
            HAVING cnt >= :min_obs
            ORDER BY indicator
        """),
        {"geo_code": geo_code, "min_obs": min_observations},
    ).fetchall()

    return [r.indicator for r in rows]
