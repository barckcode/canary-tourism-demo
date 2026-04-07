"""APScheduler job configuration.

Configures scheduled jobs for automatic data fetching from
ISTAC, INE, and CKAN sources, plus daily health checks.
"""

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level scheduler instance
scheduler: BackgroundScheduler | None = None


def _run_async(coro_func):
    """Helper to run an async pipeline function in a sync APScheduler job."""
    def wrapper():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro_func())
                logger.info("Job %s completed: %s", coro_func.__name__, result)
            finally:
                loop.close()
        except Exception:
            # Log with full traceback. The exception is intentionally
            # swallowed: if it propagates, APScheduler may permanently
            # de-schedule the job after repeated failures.
            logger.exception(
                "Job %s failed — exception swallowed to prevent "
                "APScheduler from removing the job",
                coro_func.__name__,
            )
    wrapper.__name__ = coro_func.__name__
    return wrapper


def _run_retrain_check():
    """Sync job that checks if models need retraining and retrains if so."""
    try:
        from app.db.database import SessionLocal
        from app.models.trainer import retrain_if_needed

        db = SessionLocal()
        try:
            result = retrain_if_needed(db)
            logger.info("Retrain check result: %s", result)
        finally:
            db.close()
    except Exception:
        # Log with full traceback. The exception is intentionally
        # swallowed: if it propagates, APScheduler may permanently
        # de-schedule the job after repeated failures.
        logger.exception(
            "Retrain check job failed — exception swallowed to prevent "
            "APScheduler from removing the job"
        )


def setup_scheduler() -> BackgroundScheduler:
    """Configure and start APScheduler jobs.

    Schedule:
    - fetch_istac_indicators: Every Monday 00:00 UTC
    - fetch_ine_series: Every Monday 00:30 UTC
    - fetch_egt_microdata: 1st and 15th of each month
    - fetch_cabildo_datasets: 1st of each month
    - health_check: Daily 06:00 UTC

    Returns:
        The configured and started BackgroundScheduler instance.
    """
    global scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled via settings.")
        return None

    from app.etl.pipeline import (
        run_cabildo_pipeline,
        run_ckan_microdata_pipeline,
        run_health_check,
        run_ine_pipeline,
        run_istac_pipeline,
    )

    scheduler = BackgroundScheduler(timezone="UTC")

    # ISTAC indicators: Every Monday at 00:00 UTC
    scheduler.add_job(
        _run_async(run_istac_pipeline),
        trigger=CronTrigger(day_of_week="mon", hour=0, minute=0),
        id="fetch_istac_indicators",
        name="Fetch ISTAC indicators",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour grace period
    )

    # INE series: Every Monday at 00:30 UTC
    scheduler.add_job(
        _run_async(run_ine_pipeline),
        trigger=CronTrigger(day_of_week="mon", hour=0, minute=30),
        id="fetch_ine_series",
        name="Fetch INE series",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # EGT microdata: 1st and 15th of each month at 01:00 UTC
    scheduler.add_job(
        _run_async(run_ckan_microdata_pipeline),
        trigger=CronTrigger(day="1,15", hour=1, minute=0),
        id="fetch_egt_microdata",
        name="Fetch EGT microdata from CKAN",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=7200,  # 2 hour grace period
    )

    # Cabildo datasets: 1st of each month at 02:00 UTC
    scheduler.add_job(
        _run_async(run_cabildo_pipeline),
        trigger=CronTrigger(day="1", hour=2, minute=0),
        id="fetch_cabildo_datasets",
        name="Fetch Cabildo datasets",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=7200,
    )

    # Model retraining check: Daily at 04:00 UTC (after ETL jobs)
    scheduler.add_job(
        _run_retrain_check,
        trigger=CronTrigger(hour=4, minute=0),
        id="retrain_check",
        name="Check if models need retraining",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Health check: Daily at 06:00 UTC
    scheduler.add_job(
        _run_async(run_health_check),
        trigger=CronTrigger(hour=6, minute=0),
        id="health_check",
        name="Daily health check",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info(
        "Scheduler started with %d jobs.", len(scheduler.get_jobs())
    )

    for job in scheduler.get_jobs():
        logger.info(
            "  Job '%s' (%s) — next run: %s",
            job.name,
            job.id,
            job.next_run_time,
        )

    return scheduler


def shutdown_scheduler():
    """Gracefully shut down the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down.")
        scheduler = None


def get_scheduler_status() -> dict:
    """Get current scheduler status and job information.

    Returns:
        Dict with scheduler running state and job details.
    """
    if scheduler is None or not scheduler.running:
        return {"running": False, "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
        )

    return {"running": True, "jobs": jobs}
