"""Shared database query helpers used by multiple model modules.

Extracts common data-loading patterns so that trainer.py and
scenario_engine.py (and future modules) use the same logic.
"""

import re

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


def load_arrivals_series(db: Session) -> pd.Series:
    """Load monthly tourist arrivals from DB as a pandas Series with PeriodIndex.

    Queries the time_series table for the 'turistas' indicator at geo_code
    'ES709', filtering to monthly (YYYY-MM) periods only.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        A pandas Series with PeriodIndex (freq='M') and float values,
        named 'turistas'.
    """
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
            ORDER BY period
        """)
    ).fetchall()

    # Filter only YYYY-MM format (exclude annual totals)
    monthly = [(r.period, r.value) for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)]

    periods = pd.PeriodIndex([p for p, _ in monthly], freq="M")
    values = np.array([v for _, v in monthly], dtype=float)

    return pd.Series(values, index=periods, name="turistas")
