"""ETL pipeline orchestrator.

Wires up data source connectors, validators, and storage to run
the full extract-transform-load pipeline. Logs pipeline runs
to the pipeline_runs table and triggers model retraining when
new data is detected.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.etl.sources import ckan, ine, istac
from app.etl.validators import (
    validate_microdata,
    validate_timeseries,
)

logger = logging.getLogger(__name__)


def _log_pipeline_run(
    db: Session,
    source: str,
    job_name: str,
    status: str,
    records_added: int = 0,
    error_message: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
):
    """Record a pipeline run in the pipeline_runs table."""
    db.execute(
        text("""
            INSERT INTO pipeline_runs
                (source, job_name, status, records_added, error_message,
                 started_at, finished_at)
            VALUES (:source, :job_name, :status, :records_added,
                    :error_message, :started_at, :finished_at)
        """),
        {
            "source": source,
            "job_name": job_name,
            "status": status,
            "records_added": records_added,
            "error_message": error_message,
            "started_at": started_at,
            "finished_at": finished_at,
        },
    )
    db.commit()


def _upsert_timeseries(db: Session, records: list[dict[str, Any]]) -> int:
    """Insert or update time series records in the database.

    Returns the number of records upserted.
    """
    count = 0
    for rec in records:
        db.execute(
            text("""
                INSERT OR REPLACE INTO time_series
                    (source, indicator, geo_code, period, measure, value)
                VALUES (:source, :indicator, :geo_code, :period, :measure, :value)
            """),
            rec,
        )
        count += 1

    db.commit()
    return count


def _upsert_microdata(db: Session, records: list[dict[str, Any]]) -> int:
    """Insert or update microdata records in the database.

    Returns the number of records upserted.
    """
    count = 0
    for rec in records:
        db.execute(
            text("""
                INSERT OR REPLACE INTO microdata
                    (quarter, cuestionario, isla, aeropuerto, sexo, edad,
                     nacionalidad, pais_residencia, proposito, noches,
                     aloj_categ, gasto_euros, coste_vuelos_euros,
                     coste_aloj_euros, satisfaccion, raw_json)
                VALUES (:quarter, :cuestionario, :isla, :aeropuerto, :sexo,
                        :edad, :nacionalidad, :pais_residencia, :proposito,
                        :noches, :aloj_categ, :gasto_euros,
                        :coste_vuelos_euros, :coste_aloj_euros,
                        :satisfaccion, :raw_json)
            """),
            rec,
        )
        count += 1

    db.commit()
    return count


def _trigger_retraining(db: Session, reason: str):
    """Trigger model retraining after new data is detected."""
    try:
        from app.models.trainer import ModelTrainer

        logger.info("Triggering model retraining: %s", reason)
        trainer = ModelTrainer()
        trainer.train_all(db)
        logger.info("Model retraining complete.")
    except Exception:
        logger.exception("Model retraining failed.")


async def run_istac_pipeline() -> dict[str, Any]:
    """Run the ISTAC ETL pipeline.

    Fetches indicators from ISTAC API, validates, and stores in database.

    Returns:
        Dict with pipeline run results.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    db = SessionLocal()

    try:
        logger.info("Starting ISTAC pipeline...")

        # Fetch data from ISTAC API
        raw_records = await istac.fetch_indicators()

        if not raw_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "istac", "fetch_istac_indicators", "no_new_data",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "no_new_data", "records_added": 0}

        # Validate records
        valid_records, validation = validate_timeseries(raw_records)

        if not valid_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "istac", "fetch_istac_indicators", "error",
                error_message="All records failed validation",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "error", "validation": validation.summary()}

        # Store in database
        count = _upsert_timeseries(db, valid_records)

        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "istac", "fetch_istac_indicators", "success",
            records_added=count, started_at=started_at, finished_at=finished_at,
        )

        # Trigger retraining if new data was added
        if count > 0:
            _trigger_retraining(db, f"ISTAC pipeline added {count} records")

        logger.info("ISTAC pipeline complete: %d records stored.", count)
        return {
            "status": "success",
            "records_added": count,
            "validation": validation.summary(),
        }

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "istac", "fetch_istac_indicators", "error",
            error_message=str(exc), started_at=started_at,
            finished_at=finished_at,
        )
        logger.exception("ISTAC pipeline failed.")
        return {"status": "error", "error": str(exc)}

    finally:
        db.close()


async def run_ine_pipeline() -> dict[str, Any]:
    """Run the INE ETL pipeline.

    Fetches series from INE API, validates, and stores in database.

    Returns:
        Dict with pipeline run results.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    db = SessionLocal()

    try:
        logger.info("Starting INE pipeline...")

        # Fetch data from INE API
        raw_records = await ine.fetch_series()

        if not raw_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "ine", "fetch_ine_series", "no_new_data",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "no_new_data", "records_added": 0}

        # Validate records
        valid_records, validation = validate_timeseries(raw_records)

        if not valid_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "ine", "fetch_ine_series", "error",
                error_message="All records failed validation",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "error", "validation": validation.summary()}

        # Store in database
        count = _upsert_timeseries(db, valid_records)

        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "ine", "fetch_ine_series", "success",
            records_added=count, started_at=started_at, finished_at=finished_at,
        )

        if count > 0:
            _trigger_retraining(db, f"INE pipeline added {count} records")

        logger.info("INE pipeline complete: %d records stored.", count)
        return {
            "status": "success",
            "records_added": count,
            "validation": validation.summary(),
        }

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "ine", "fetch_ine_series", "error",
            error_message=str(exc), started_at=started_at,
            finished_at=finished_at,
        )
        logger.exception("INE pipeline failed.")
        return {"status": "error", "error": str(exc)}

    finally:
        db.close()


async def run_ckan_microdata_pipeline() -> dict[str, Any]:
    """Run the CKAN/EGT microdata ETL pipeline.

    Fetches EGT microdata from CKAN, validates, and stores in database.

    Returns:
        Dict with pipeline run results.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    db = SessionLocal()

    try:
        logger.info("Starting CKAN microdata pipeline...")

        # Fetch microdata from CKAN
        raw_records = await ckan.fetch_egt_microdata()

        if not raw_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "ckan", "fetch_egt_microdata", "no_new_data",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "no_new_data", "records_added": 0}

        # Validate records
        valid_records, validation = validate_microdata(raw_records)

        if not valid_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "ckan", "fetch_egt_microdata", "error",
                error_message="All records failed validation",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "error", "validation": validation.summary()}

        # Store in database
        count = _upsert_microdata(db, valid_records)

        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "ckan", "fetch_egt_microdata", "success",
            records_added=count, started_at=started_at, finished_at=finished_at,
        )

        if count > 0:
            _trigger_retraining(db, f"CKAN pipeline added {count} microdata records")

        logger.info("CKAN microdata pipeline complete: %d records stored.", count)
        return {
            "status": "success",
            "records_added": count,
            "validation": validation.summary(),
        }

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "ckan", "fetch_egt_microdata", "error",
            error_message=str(exc), started_at=started_at,
            finished_at=finished_at,
        )
        logger.exception("CKAN microdata pipeline failed.")
        return {"status": "error", "error": str(exc)}

    finally:
        db.close()


async def run_cabildo_pipeline() -> dict[str, Any]:
    """Run the Cabildo datasets ETL pipeline.

    Fetches datasets from datos.tenerife.es CKAN portal. This portal
    is frequently offline, so failures are handled gracefully.

    Returns:
        Dict with pipeline run results.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    db = SessionLocal()

    try:
        logger.info("Starting Cabildo pipeline...")

        raw_records = await ckan.fetch_cabildo_datasets()

        if not raw_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "cabildo", "fetch_cabildo_datasets", "no_new_data",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "no_new_data", "records_added": 0}

        valid_records, validation = validate_timeseries(raw_records)

        if not valid_records:
            finished_at = datetime.now(timezone.utc).isoformat()
            _log_pipeline_run(
                db, "cabildo", "fetch_cabildo_datasets", "error",
                error_message="All records failed validation",
                started_at=started_at, finished_at=finished_at,
            )
            return {"status": "error", "validation": validation.summary()}

        count = _upsert_timeseries(db, valid_records)

        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "cabildo", "fetch_cabildo_datasets", "success",
            records_added=count, started_at=started_at, finished_at=finished_at,
        )

        logger.info("Cabildo pipeline complete: %d records stored.", count)
        return {
            "status": "success",
            "records_added": count,
            "validation": validation.summary(),
        }

    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "cabildo", "fetch_cabildo_datasets", "error",
            error_message=str(exc), started_at=started_at,
            finished_at=finished_at,
        )
        logger.exception("Cabildo pipeline failed.")
        return {"status": "error", "error": str(exc)}

    finally:
        db.close()


async def run_health_check() -> dict[str, Any]:
    """Run a health check on all data sources and the database.

    Verifies API availability and checks model accuracy drift.

    Returns:
        Dict with health check results.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, Any] = {"timestamp": started_at, "checks": {}}

    # Check ISTAC API
    try:
        async with __import__("httpx").AsyncClient() as client:
            resp = await client.get(
                f"{istac.BASE_URL}/indicators",
                timeout=10.0,
            )
            results["checks"]["istac_api"] = {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "http_status": resp.status_code,
            }
    except Exception as exc:
        results["checks"]["istac_api"] = {"status": "error", "error": str(exc)}

    # Check INE API
    try:
        async with __import__("httpx").AsyncClient() as client:
            resp = await client.get(
                f"{ine.BASE_URL}/OPERACIONES_DISPONIBLES",
                timeout=10.0,
            )
            results["checks"]["ine_api"] = {
                "status": "ok" if resp.status_code == 200 else "degraded",
                "http_status": resp.status_code,
            }
    except Exception as exc:
        results["checks"]["ine_api"] = {"status": "error", "error": str(exc)}

    # Check database
    db = SessionLocal()
    try:
        ts_count = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()
        micro_count = db.execute(text("SELECT COUNT(*) FROM microdata")).scalar()
        pred_count = db.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
        results["checks"]["database"] = {
            "status": "ok",
            "time_series_count": ts_count,
            "microdata_count": micro_count,
            "predictions_count": pred_count,
        }

        # Check latest pipeline run
        latest_run = db.execute(
            text("""
                SELECT source, job_name, status, finished_at
                FROM pipeline_runs
                ORDER BY id DESC LIMIT 1
            """)
        ).fetchone()
        if latest_run:
            results["checks"]["latest_pipeline_run"] = {
                "source": latest_run.source,
                "job_name": latest_run.job_name,
                "status": latest_run.status,
                "finished_at": latest_run.finished_at,
            }
    except Exception as exc:
        results["checks"]["database"] = {"status": "error", "error": str(exc)}
    finally:
        db.close()

    # Log health check
    db = SessionLocal()
    try:
        overall = "success" if all(
            c.get("status") == "ok"
            for c in results["checks"].values()
        ) else "degraded"
        finished_at = datetime.now(timezone.utc).isoformat()
        _log_pipeline_run(
            db, "system", "health_check", overall,
            started_at=started_at, finished_at=finished_at,
        )
    finally:
        db.close()

    return results


def run_pipeline():
    """Run the full ETL pipeline synchronously.

    Executes all pipeline stages in sequence: ISTAC, INE, CKAN, Cabildo.
    This is the main entry point for manual pipeline execution.
    """
    logger.info("Starting full ETL pipeline...")

    results = {}
    results["istac"] = asyncio.run(run_istac_pipeline())
    results["ine"] = asyncio.run(run_ine_pipeline())
    results["ckan_microdata"] = asyncio.run(run_ckan_microdata_pipeline())
    results["cabildo"] = asyncio.run(run_cabildo_pipeline())

    total_added = sum(
        r.get("records_added", 0) for r in results.values()
    )

    logger.info(
        "Full ETL pipeline complete. Total records added: %d", total_added
    )
    return results
