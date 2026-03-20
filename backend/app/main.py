"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.api.schemas import DetailedHealthResponse, ReadinessResponse
from app.config import settings
from app.db.database import get_db, init_db
from app.db.models import PipelineRun, Prediction, Profile, TimeSeries, TrainingRun
from app.etl.scheduler import setup_scheduler, shutdown_scheduler
from app.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    from sqlalchemy import text

    from app.db.database import SessionLocal

    logger.info("Initializing database...")
    init_db()

    # Auto-seed if database is empty
    db = SessionLocal()
    try:
        count = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()
        if count == 0:
            logger.info("Database is empty — running data seed...")
            from app.db.seed import seed_all

            seed_all(db)
            logger.info("Data seed complete.")

        # Seed tourism events if table is empty
        from app.db.events_seed import seed_events

        seed_events(db)

        # Train or retrain models if needed (new data or no prior training)
        from app.models.trainer import retrain_if_needed

        result = retrain_if_needed(db)
        if result.get("retrained"):
            logger.info("Model training complete (%.1fs).", result.get("duration_seconds", 0))
        else:
            logger.info("Models up to date: %s", result.get("reason", "unknown"))
    except Exception:
        logger.exception("Error during startup initialization.")
        raise
    finally:
        db.close()

    # Start background scheduler for data fetching
    setup_scheduler()

    logger.info("Application ready.")
    yield
    shutdown_scheduler()
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.getLogger(__name__).error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}


@app.get("/health/detailed", response_model=DetailedHealthResponse)
def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check that verifies database, ML models, ETL freshness, and data availability.

    Returns an overall status of 'ok', 'degraded', or 'unhealthy' based on system state.
    Use this endpoint for monitoring dashboards and alerting.
    """
    now = datetime.now(timezone.utc).isoformat()

    # --- Database check ---
    try:
        ts_count = db.query(func.count(TimeSeries.id)).scalar() or 0
        pred_count = db.query(func.count(Prediction.id)).scalar() or 0
        prof_count = db.query(func.count(Profile.id)).scalar() or 0
        db_status = "ok"
    except Exception:
        logger.exception("Database health check failed")
        return DetailedHealthResponse(
            status="unhealthy",
            timestamp=now,
            database={"status": "error", "time_series_count": 0, "predictions_count": 0, "profiles_count": 0},
            models={"forecaster": {"status": "not_trained"}, "profiler": {"status": "not_trained", "clusters": 0}},
            etl={"last_success": None, "last_failure": None},
            data_freshness={"latest_period": None, "days_since_update": None},
        )

    # --- Models check ---
    forecaster_status = "ok" if pred_count > 0 else "not_trained"
    profiler_status = "ok" if prof_count > 0 else "not_trained"
    cluster_count = db.query(func.count(func.distinct(Profile.cluster_id))).scalar() or 0

    last_training_run = (
        db.query(TrainingRun)
        .filter(TrainingRun.status == "success")
        .order_by(TrainingRun.trained_at.desc())
        .first()
    )
    last_training_at = last_training_run.trained_at if last_training_run else None

    # --- ETL check ---
    last_etl_success = (
        db.query(func.max(PipelineRun.finished_at))
        .filter(PipelineRun.status == "success")
        .scalar()
    )
    last_etl_failure = (
        db.query(func.max(PipelineRun.finished_at))
        .filter(PipelineRun.status == "error")
        .scalar()
    )

    # --- Data freshness ---
    latest_period = db.query(func.max(TimeSeries.period)).scalar()
    days_since_update: int | None = None
    if latest_period:
        try:
            # period format is "YYYY-MM"
            latest_date = datetime.strptime(latest_period, "%Y-%m").replace(tzinfo=timezone.utc)
            days_since_update = (datetime.now(timezone.utc) - latest_date).days
        except ValueError:
            days_since_update = None

    # --- Overall status ---
    models_not_trained = forecaster_status == "not_trained" or profiler_status == "not_trained"
    data_stale = days_since_update is not None and days_since_update > 30

    if db_status != "ok":
        overall = "unhealthy"
    elif models_not_trained or data_stale:
        overall = "degraded"
    else:
        overall = "ok"

    return DetailedHealthResponse(
        status=overall,
        timestamp=now,
        database={
            "status": db_status,
            "time_series_count": ts_count,
            "predictions_count": pred_count,
            "profiles_count": prof_count,
        },
        models={
            "forecaster": {"status": forecaster_status, "last_training": last_training_at},
            "profiler": {"status": profiler_status, "clusters": cluster_count},
        },
        etl={
            "last_success": last_etl_success,
            "last_failure": last_etl_failure,
        },
        data_freshness={
            "latest_period": latest_period,
            "days_since_update": days_since_update,
        },
    )


@app.get("/health/readiness", response_model=ReadinessResponse)
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe for orchestrators (e.g. Kubernetes).

    Returns HTTP 200 if the system has data and trained models, HTTP 503 otherwise.
    """
    try:
        ts_count = db.query(func.count(TimeSeries.id)).scalar() or 0
        pred_count = db.query(func.count(Prediction.id)).scalar() or 0
        prof_count = db.query(func.count(Profile.id)).scalar() or 0
    except Exception:
        logger.exception("Readiness probe database query failed")
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "Database unreachable"},
        )

    if ts_count == 0:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": "No time series data available"},
        )

    if pred_count == 0 or prof_count == 0:
        missing = []
        if pred_count == 0:
            missing.append("predictions")
        if prof_count == 0:
            missing.append("profiles")
        return JSONResponse(
            status_code=503,
            content={"ready": False, "reason": f"Models not trained: missing {', '.join(missing)}"},
        )

    return ReadinessResponse(ready=True)
