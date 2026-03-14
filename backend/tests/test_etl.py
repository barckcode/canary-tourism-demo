"""Tests for ETL pipeline components.

Tests cover:
- ISTAC connector (mock HTTP responses)
- INE connector (mock HTTP responses)
- CKAN connector (mock HTTP responses)
- Validators (schema, range, completeness, dedup)
- Pipeline orchestration
- Scheduler job registration
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.etl.sources import ckan, ine, istac
from app.etl.validators import (
    ValidationResult,
    check_completeness,
    validate_microdata,
    validate_timeseries,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Helper to run async functions in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# ISTAC connector tests
# ---------------------------------------------------------------------------


class TestISTACConnector:
    """Tests for the ISTAC API connector."""

    def test_parse_observations_list_format(self):
        """Should parse observations from a list-format response."""
        data = {
            "dimension": {
                "TIME": {
                    "dimensionValues": {
                        "value": [
                            {"id": "2025-01", "order": 0},
                            {"id": "2025-02", "order": 1},
                        ]
                    }
                },
                "GEOGRAPHICAL": {
                    "dimensionValues": {
                        "value": [{"id": "ES709", "order": 0}]
                    }
                },
                "MEASURE": {
                    "dimensionValues": {
                        "value": [{"id": "ABSOLUTE", "order": 0}]
                    }
                },
            },
            "observation": [
                {"timeIndex": 0, "geographicalIndex": 0, "measureIndex": 0, "value": 500000.0},
                {"timeIndex": 1, "geographicalIndex": 0, "measureIndex": 0, "value": 550000.0},
            ],
        }

        records = istac._parse_observations(data, "TURISTAS")
        assert len(records) == 2
        assert records[0]["source"] == "istac"
        assert records[0]["indicator"] == "turistas"
        assert records[0]["geo_code"] == "ES709"
        assert records[0]["period"] == "2025-01"
        assert records[0]["value"] == 500000.0
        assert records[1]["period"] == "2025-02"
        assert records[1]["value"] == 550000.0

    def test_parse_observations_dict_format(self):
        """Should parse observations from a dict-keyed response."""
        data = {
            "dimension": {
                "TIME": {
                    "dimensionValues": {
                        "value": [
                            {"id": "2024-12", "order": 0},
                        ]
                    }
                },
                "GEOGRAPHICAL": {
                    "dimensionValues": {
                        "value": [{"id": "ES709", "order": 0}]
                    }
                },
                "MEASURE": {
                    "dimensionValues": {
                        "value": [{"id": "ABSOLUTE", "order": 0}]
                    }
                },
            },
            "observation": {"0|0|0": 687000.0},
        }

        records = istac._parse_observations(data, "TURISTAS")
        assert len(records) == 1
        assert records[0]["value"] == 687000.0
        assert records[0]["period"] == "2024-12"

    def test_parse_observations_skips_null_values(self):
        """Should skip observations with None values."""
        data = {
            "dimension": {
                "TIME": {"dimensionValues": {"value": [{"id": "2025-01", "order": 0}]}},
                "GEOGRAPHICAL": {"dimensionValues": {"value": [{"id": "ES709"}]}},
                "MEASURE": {"dimensionValues": {"value": [{"id": "ABSOLUTE"}]}},
            },
            "observation": [
                {"timeIndex": 0, "geographicalIndex": 0, "measureIndex": 0, "value": None},
            ],
        }
        records = istac._parse_observations(data, "TURISTAS")
        assert len(records) == 0

    def test_get_last_update(self):
        """Should extract lastUpdate from metadata."""
        assert istac.get_last_update({"lastUpdate": "2025-03-01"}) == "2025-03-01"
        assert istac.get_last_update({"lastUpdated": "2025-03-01"}) == "2025-03-01"
        assert istac.get_last_update({}) is None

    def test_fetch_indicators_with_mock(self):
        """Should fetch and parse indicators from mocked API."""
        mock_data = {
            "dimension": {
                "TIME": {"dimensionValues": {"value": [{"id": "2025-01", "order": 0}]}},
                "GEOGRAPHICAL": {"dimensionValues": {"value": [{"id": "ES709"}]}},
                "MEASURE": {"dimensionValues": {"value": [{"id": "ABSOLUTE"}]}},
            },
            "observation": [
                {"timeIndex": 0, "geographicalIndex": 0, "measureIndex": 0, "value": 100.0},
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            records = _run_async(istac.fetch_indicators(["TURISTAS"]))
            assert len(records) == 1
            assert records[0]["indicator"] == "turistas"


# ---------------------------------------------------------------------------
# INE connector tests
# ---------------------------------------------------------------------------


class TestINEConnector:
    """Tests for the INE API connector."""

    def test_parse_period_monthly(self):
        """Should parse monthly periods correctly."""
        rec = {"Anyo": 2025, "FK_Periodo": 3}
        assert ine._parse_period(rec) == "2025-03"

    def test_parse_period_quarterly(self):
        """Should parse quarterly periods correctly."""
        rec = {"Anyo": 2025, "FK_Periodo": 19}
        assert ine._parse_period(rec) == "2025-Q1"

        rec = {"Anyo": 2024, "FK_Periodo": 22}
        assert ine._parse_period(rec) == "2024-Q4"

    def test_parse_period_invalid(self):
        """Should return None for invalid period codes."""
        assert ine._parse_period({"Anyo": 2025, "FK_Periodo": 99}) is None
        assert ine._parse_period({"Anyo": None, "FK_Periodo": 1}) is None
        assert ine._parse_period({}) is None

    def test_parse_series_records(self):
        """Should parse INE JSON data into TimeSeries records."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 150000.0},
            {"Anyo": 2025, "FK_Periodo": 2, "Valor": 160000.0},
            {"Anyo": 2025, "FK_Periodo": 3, "Valor": None},  # Should be skipped
        ]

        records = ine._parse_series_records(data, "hotel_viajeros", "ES709")
        assert len(records) == 2
        assert records[0]["source"] == "ine"
        assert records[0]["indicator"] == "hotel_viajeros"
        assert records[0]["period"] == "2025-01"
        assert records[0]["value"] == 150000.0
        assert records[1]["period"] == "2025-02"

    def test_fetch_series_with_mock(self):
        """Should fetch and parse series from mocked API."""
        mock_data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 50000.0},
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            series = [("EOH3949", "hotel_viajeros_tenerife", "ES709")]
            records = _run_async(ine.fetch_series(series))
            assert len(records) == 1
            assert records[0]["indicator"] == "hotel_viajeros_tenerife"


# ---------------------------------------------------------------------------
# CKAN connector tests
# ---------------------------------------------------------------------------


class TestCKANConnector:
    """Tests for the CKAN API connector."""

    def test_extract_quarter_standard(self):
        """Should extract quarter from standard formats."""
        resource = {"name": "microdatos_2024Q3", "description": ""}
        assert ckan._extract_quarter_from_resource(resource) == "2024Q3"

    def test_extract_quarter_trimestre(self):
        """Should extract quarter from Spanish trimestre format."""
        resource = {"name": "", "description": "3er TRIMESTRE 2024"}
        assert ckan._extract_quarter_from_resource(resource) == "2024Q3"

    def test_extract_quarter_t_format(self):
        """Should extract quarter from T3 2024 format."""
        resource = {"name": "datos_T2 2025", "description": ""}
        assert ckan._extract_quarter_from_resource(resource) == "2025Q2"

    def test_extract_quarter_no_match(self):
        """Should return None when quarter cannot be extracted."""
        resource = {"name": "some_data", "description": "no quarter info"}
        assert ckan._extract_quarter_from_resource(resource) is None

    def test_parse_microdata_row_tenerife(self):
        """Should parse a valid Tenerife microdata row."""
        row = {
            "ISLA": "ES709",
            "NUMERO_CUESTIONARIO": "12345",
            "AEROPUERTO_ORIGEN": "TFN",
            "SEXO": "1",
            "EDAD": "45",
            "NACIONALIDAD": "GB",
            "PAIS_RESIDENCIA": "GB",
            "PROPOSITO": "OCIO",
            "NOCHES": "7",
            "ALOJ_CATEG": "HOTEL_4",
            "GASTO_EUROS": "1200.50",
            "COSTE_VUELOS_EUROS": "350.00",
            "COSTE_ALOJ_EUROS": "580.00",
            "SATISFACCION": "9",
        }

        record = ckan._parse_microdata_row(row, "2025Q1")
        assert record is not None
        assert record["quarter"] == "2025Q1"
        assert record["cuestionario"] == 12345
        assert record["isla"] == "ES709"
        assert record["edad"] == 45
        assert record["gasto_euros"] == 1200.50

    def test_parse_microdata_row_non_tenerife(self):
        """Should return None for non-Tenerife records."""
        row = {"ISLA": "ES708", "NUMERO_CUESTIONARIO": "99999"}
        assert ckan._parse_microdata_row(row, "2025Q1") is None

    def test_parse_microdata_row_missing_cuestionario(self):
        """Should return None when cuestionario is missing."""
        row = {"ISLA": "ES709", "NUMERO_CUESTIONARIO": "_Z"}
        assert ckan._parse_microdata_row(row, "2025Q1") is None

    def test_safe_int(self):
        """Should handle int conversion safely."""
        assert ckan._safe_int("42") == 42
        assert ckan._safe_int("42.7") == 42
        assert ckan._safe_int("_Z") is None
        assert ckan._safe_int("") is None
        assert ckan._safe_int("abc") is None

    def test_safe_float(self):
        """Should handle float conversion safely."""
        assert ckan._safe_float("42.5") == 42.5
        assert ckan._safe_float("_U") is None
        assert ckan._safe_float("") is None


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


class TestValidators:
    """Tests for data quality validators."""

    def test_validate_timeseries_valid_records(self):
        """Should accept valid time series records."""
        records = [
            {
                "source": "istac",
                "indicator": "turistas",
                "geo_code": "ES709",
                "period": "2025-01",
                "measure": "ABSOLUTE",
                "value": 687000.0,
            },
            {
                "source": "ine",
                "indicator": "hotel_viajeros",
                "geo_code": "ES709",
                "period": "2025-02",
                "measure": "ABSOLUTE",
                "value": 150000.0,
            },
        ]

        valid, result = validate_timeseries(records)
        assert len(valid) == 2
        assert result.is_valid
        assert result.records_valid == 2
        assert result.records_dropped == 0

    def test_validate_timeseries_missing_fields(self):
        """Should reject records with missing required fields."""
        records = [
            {"source": "istac", "indicator": "turistas"},  # Missing fields
        ]

        valid, result = validate_timeseries(records)
        assert len(valid) == 0
        assert not result.is_valid
        assert result.records_dropped == 1

    def test_validate_timeseries_invalid_value_type(self):
        """Should reject records with non-numeric values."""
        records = [
            {
                "source": "istac",
                "indicator": "turistas",
                "geo_code": "ES709",
                "period": "2025-01",
                "measure": "ABSOLUTE",
                "value": "not_a_number",
            },
        ]

        valid, result = validate_timeseries(records)
        assert len(valid) == 0

    def test_validate_timeseries_deduplication(self):
        """Should remove duplicate records."""
        record = {
            "source": "istac",
            "indicator": "turistas",
            "geo_code": "ES709",
            "period": "2025-01",
            "measure": "ABSOLUTE",
            "value": 500000.0,
        }
        records = [record.copy(), record.copy(), record.copy()]

        valid, result = validate_timeseries(records)
        assert len(valid) == 1
        assert result.duplicates_removed == 2

    def test_validate_timeseries_year_range(self):
        """Should reject records with years outside valid range."""
        records = [
            {
                "source": "istac",
                "indicator": "turistas",
                "geo_code": "ES709",
                "period": "1800-01",
                "measure": "ABSOLUTE",
                "value": 100.0,
            },
        ]

        valid, result = validate_timeseries(records)
        assert len(valid) == 0

    def test_validate_timeseries_normalizes_case(self):
        """Should normalize source and indicator to lowercase."""
        records = [
            {
                "source": "ISTAC",
                "indicator": "TURISTAS",
                "geo_code": "ES709",
                "period": "2025-01",
                "measure": "ABSOLUTE",
                "value": 100.0,
            },
        ]

        valid, result = validate_timeseries(records)
        assert valid[0]["source"] == "istac"
        assert valid[0]["indicator"] == "turistas"

    def test_validate_microdata_valid_records(self):
        """Should accept valid microdata records."""
        records = [
            {
                "quarter": "2025Q1",
                "cuestionario": 12345,
                "isla": "ES709",
                "edad": 35,
                "gasto_euros": 800.0,
                "noches": 7,
            },
        ]

        valid, result = validate_microdata(records)
        assert len(valid) == 1
        assert result.is_valid

    def test_validate_microdata_missing_quarter(self):
        """Should reject records without quarter."""
        records = [{"cuestionario": 12345}]

        valid, result = validate_microdata(records)
        assert len(valid) == 0

    def test_validate_microdata_deduplication(self):
        """Should remove duplicate microdata records."""
        record = {"quarter": "2025Q1", "cuestionario": 12345}
        records = [record.copy(), record.copy()]

        valid, result = validate_microdata(records)
        assert len(valid) == 1
        assert result.duplicates_removed == 1

    def test_check_completeness_no_gaps(self):
        """Should find no gaps in a complete series."""
        records = [
            {"indicator": "turistas", "period": "2025-01"},
            {"indicator": "turistas", "period": "2025-02"},
            {"indicator": "turistas", "period": "2025-03"},
        ]

        missing = check_completeness(records, "turistas")
        assert missing == []

    def test_check_completeness_with_gaps(self):
        """Should detect missing periods in a series."""
        records = [
            {"indicator": "turistas", "period": "2025-01"},
            {"indicator": "turistas", "period": "2025-03"},
            # 2025-02 is missing
        ]

        missing = check_completeness(records, "turistas")
        assert "2025-02" in missing

    def test_check_completeness_empty_data(self):
        """Should handle empty data gracefully."""
        missing = check_completeness([], "turistas")
        assert missing == []


# ---------------------------------------------------------------------------
# Pipeline orchestration tests
# ---------------------------------------------------------------------------


class TestPipeline:
    """Tests for pipeline orchestration."""

    def test_log_pipeline_run(self, db):
        """Should log a pipeline run to the database."""
        from sqlalchemy import text as sql_text

        from app.etl.pipeline import _log_pipeline_run

        _log_pipeline_run(
            db,
            source="test",
            job_name="test_job",
            status="success",
            records_added=42,
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )

        row = db.execute(
            sql_text("""
                SELECT source, job_name, status, records_added
                FROM pipeline_runs
                WHERE source='test' AND job_name='test_job'
                ORDER BY id DESC LIMIT 1
            """)
        ).fetchone()

        assert row is not None
        assert row.source == "test"
        assert row.job_name == "test_job"
        assert row.status == "success"
        assert row.records_added == 42

    def test_upsert_timeseries(self, db):
        """Should insert new time series records."""
        from sqlalchemy import text as sql_text

        from app.etl.pipeline import _upsert_timeseries

        records = [
            {
                "source": "test_etl",
                "indicator": "test_indicator",
                "geo_code": "TEST",
                "period": "9999-01",
                "measure": "ABSOLUTE",
                "value": 42.0,
            }
        ]

        count = _upsert_timeseries(db, records)
        assert count == 1

        row = db.execute(
            sql_text("""
                SELECT value FROM time_series
                WHERE source='test_etl' AND indicator='test_indicator'
                AND period='9999-01'
            """)
        ).fetchone()
        assert row is not None
        assert row.value == 42.0

        # Cleanup
        db.execute(
            sql_text("DELETE FROM time_series WHERE source='test_etl'")
        )
        db.commit()

    def test_upsert_timeseries_replaces_existing(self, db):
        """Should replace existing records on upsert."""
        from sqlalchemy import text as sql_text

        from app.etl.pipeline import _upsert_timeseries

        record = {
            "source": "test_etl",
            "indicator": "test_replace",
            "geo_code": "TEST",
            "period": "9999-01",
            "measure": "ABSOLUTE",
            "value": 100.0,
        }

        _upsert_timeseries(db, [record])

        # Update with new value
        record["value"] = 200.0
        _upsert_timeseries(db, [record])

        row = db.execute(
            sql_text("""
                SELECT value FROM time_series
                WHERE source='test_etl' AND indicator='test_replace'
                AND period='9999-01'
            """)
        ).fetchone()
        assert row.value == 200.0

        # Cleanup
        db.execute(
            sql_text("DELETE FROM time_series WHERE source='test_etl'")
        )
        db.commit()

    def test_run_pipeline_sync(self):
        """Should execute run_pipeline without errors (mocked connectors)."""
        mock_result = {"status": "success", "records_added": 0}

        async def mock_istac():
            return mock_result

        async def mock_ine():
            return mock_result

        async def mock_ckan():
            return mock_result

        async def mock_cabildo():
            return mock_result

        with patch("app.etl.pipeline.run_istac_pipeline", mock_istac), \
             patch("app.etl.pipeline.run_ine_pipeline", mock_ine), \
             patch("app.etl.pipeline.run_ckan_microdata_pipeline", mock_ckan), \
             patch("app.etl.pipeline.run_cabildo_pipeline", mock_cabildo):

            from app.etl.pipeline import run_pipeline
            results = run_pipeline()
            assert "istac" in results
            assert "ine" in results
            assert results["istac"]["status"] == "success"


# ---------------------------------------------------------------------------
# Scheduler tests
# ---------------------------------------------------------------------------


class TestScheduler:
    """Tests for scheduler configuration."""

    def test_setup_scheduler_creates_jobs(self):
        """Should create all expected jobs."""
        from app.etl.scheduler import setup_scheduler, shutdown_scheduler

        sched = setup_scheduler()
        assert sched is not None

        jobs = sched.get_jobs()
        job_ids = {job.id for job in jobs}

        assert "fetch_istac_indicators" in job_ids
        assert "fetch_ine_series" in job_ids
        assert "fetch_egt_microdata" in job_ids
        assert "fetch_cabildo_datasets" in job_ids
        assert "health_check" in job_ids

        assert len(jobs) == 5

        shutdown_scheduler()

    def test_get_scheduler_status(self):
        """Should return status with job details."""
        from app.etl.scheduler import (
            get_scheduler_status,
            setup_scheduler,
            shutdown_scheduler,
        )

        setup_scheduler()
        status = get_scheduler_status()

        assert status["running"] is True
        assert len(status["jobs"]) == 5

        for job in status["jobs"]:
            assert "id" in job
            assert "name" in job
            assert "next_run_time" in job

        shutdown_scheduler()

    def test_scheduler_disabled(self):
        """Should not start when scheduler_enabled is False."""
        from app.etl.scheduler import shutdown_scheduler

        with patch("app.etl.scheduler.settings") as mock_settings:
            mock_settings.scheduler_enabled = False

            from app.etl.scheduler import setup_scheduler
            result = setup_scheduler()
            assert result is None

        shutdown_scheduler()

    def test_shutdown_scheduler(self):
        """Should shut down cleanly."""
        from app.etl.scheduler import (
            get_scheduler_status,
            setup_scheduler,
            shutdown_scheduler,
        )

        setup_scheduler()
        shutdown_scheduler()

        status = get_scheduler_status()
        assert status["running"] is False
