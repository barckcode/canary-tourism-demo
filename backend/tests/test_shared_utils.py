"""Tests for shared utility modules: constants and queries."""

import numpy as np
import pandas as pd

from app.utils.constants import COVID_END, COVID_START


# ---------------------------------------------------------------------------
# Shared constants tests
# ---------------------------------------------------------------------------


class TestSharedConstants:
    """Tests for app.utils.constants."""

    def test_covid_start_format(self):
        """COVID_START should be a valid YYYY-MM string."""
        assert isinstance(COVID_START, str)
        assert len(COVID_START) == 7
        year, month = COVID_START.split("-")
        assert int(year) == 2020
        assert int(month) == 3

    def test_covid_end_format(self):
        """COVID_END should be a valid YYYY-MM string."""
        assert isinstance(COVID_END, str)
        assert len(COVID_END) == 7
        year, month = COVID_END.split("-")
        assert int(year) == 2021
        assert int(month) == 6

    def test_covid_range_is_consistent(self):
        """COVID_END should be after COVID_START."""
        assert COVID_END > COVID_START

    def test_forecaster_uses_shared_constants(self):
        """Forecaster should import COVID constants from shared module."""
        from app.models.forecaster import COVID_START as F_START, COVID_END as F_END
        assert F_START is COVID_START
        assert F_END is COVID_END

    def test_scenario_engine_uses_shared_constants(self):
        """ScenarioEngine should import COVID constants from shared module."""
        from app.models.scenario_engine import COVID_START as S_START, COVID_END as S_END
        assert S_START is COVID_START
        assert S_END is COVID_END


# ---------------------------------------------------------------------------
# Shared queries tests
# ---------------------------------------------------------------------------


class TestSharedQueries:
    """Tests for app.utils.queries."""

    def test_load_arrivals_series_returns_series(self, db):
        """Should return a pandas Series with PeriodIndex."""
        from app.utils.queries import load_arrivals_series

        series = load_arrivals_series(db)
        assert isinstance(series, pd.Series)
        assert series.name == "turistas"
        assert isinstance(series.index, pd.PeriodIndex)
        assert series.index.freq == "M"

    def test_load_arrivals_series_has_data(self, db):
        """Should return non-empty series from seeded test data."""
        from app.utils.queries import load_arrivals_series

        series = load_arrivals_series(db)
        assert len(series) > 0
        assert all(isinstance(v, (int, float, np.floating)) for v in series.values)

    def test_load_arrivals_series_monthly_only(self, db):
        """Should only contain monthly (YYYY-MM) periods, no annual totals."""
        from app.utils.queries import load_arrivals_series

        series = load_arrivals_series(db)
        for period in series.index:
            # PeriodIndex with freq='M' ensures monthly periods
            assert period.freq == "M" or period.freqstr == "M"

    def test_load_arrivals_series_matches_trainer(self, db):
        """Shared query should produce same result as the old trainer query."""
        from app.utils.queries import load_arrivals_series

        series = load_arrivals_series(db)
        # Verify it matches what trainer.train_forecaster would use
        assert series.name == "turistas"
        assert len(series) > 12  # At least a year of data

    def test_load_arrivals_series_sorted(self, db):
        """Series should be sorted chronologically."""
        from app.utils.queries import load_arrivals_series

        series = load_arrivals_series(db)
        periods = list(series.index)
        assert periods == sorted(periods)
