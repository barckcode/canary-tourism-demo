"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.config import settings
from app.db.database import init_db
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

        # Auto-train models if no predictions exist
        pred_count = db.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
        if pred_count == 0:
            logger.info("No predictions found — training models...")
            from app.models.trainer import ModelTrainer

            trainer = ModelTrainer()
            trainer.train_all(db)
            logger.info("Model training complete.")
    except Exception:
        logger.exception("Error during startup initialization.")
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.getLogger(__name__).error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}
