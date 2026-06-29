"""SQLite database connection and session management."""

import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.debug,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_predictions_unique_constraint(bind) -> None:
    """Add unique constraint to predictions table for existing databases.

    SQLite does not support ``ALTER TABLE ... ADD CONSTRAINT``, so we check
    whether the constraint already exists by inspecting ``sqlite_master``.
    If it is missing we recreate the table with the constraint, preserving
    all existing data.
    """
    with bind.connect() as conn:
        # Check if the predictions table exists at all
        row = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='predictions'")
        ).fetchone()
        if row is None:
            return  # Table will be created by create_all

        create_sql = row[0] or ""
        if "uq_prediction" in create_sql:
            return  # Constraint already present

        logger.info("Migrating predictions table: adding unique constraint uq_prediction")

        # Remove any existing duplicates first, keeping the row with the highest id
        conn.execute(text("""
            DELETE FROM predictions
            WHERE id NOT IN (
                SELECT MAX(id) FROM predictions
                GROUP BY model, indicator, geo_code, period, version
            )
        """))

        conn.execute(text("ALTER TABLE predictions RENAME TO _predictions_old"))
        conn.execute(text("""
            CREATE TABLE predictions (
                id INTEGER NOT NULL PRIMARY KEY,
                model VARCHAR NOT NULL,
                indicator VARCHAR NOT NULL,
                geo_code VARCHAR NOT NULL,
                period VARCHAR NOT NULL,
                value_predicted FLOAT,
                ci_lower_80 FLOAT,
                ci_upper_80 FLOAT,
                ci_lower_95 FLOAT,
                ci_upper_95 FLOAT,
                generated_at VARCHAR DEFAULT (CURRENT_TIMESTAMP),
                trained_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                version INTEGER DEFAULT 1,
                is_current BOOLEAN DEFAULT 1,
                CONSTRAINT uq_prediction UNIQUE (model, indicator, geo_code, period, version)
            )
        """))
        conn.execute(text("""
            INSERT INTO predictions
                (id, model, indicator, geo_code, period, value_predicted,
                 ci_lower_80, ci_upper_80, ci_lower_95, ci_upper_95,
                 generated_at, trained_at, version, is_current)
            SELECT id, model, indicator, geo_code, period, value_predicted,
                   ci_lower_80, ci_upper_80, ci_lower_95, ci_upper_95,
                   generated_at, trained_at, version, is_current
            FROM _predictions_old
        """))
        conn.execute(text("DROP TABLE _predictions_old"))

        # Recreate indices
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pred_model_indicator_geo "
            "ON predictions (model, indicator, geo_code)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pred_period ON predictions (period)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pred_is_current ON predictions (is_current)"
        ))

        conn.commit()
        logger.info("Migration complete: predictions table now has uq_prediction constraint")


def init_db():
    """Create all tables."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    _migrate_predictions_unique_constraint(engine)
    Base.metadata.create_all(bind=engine)
