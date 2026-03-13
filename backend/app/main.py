"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.db.database import init_db

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

    logger.info("Application ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.app_version}
