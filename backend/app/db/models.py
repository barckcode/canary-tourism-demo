"""SQLAlchemy ORM models matching the project schema."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.database import Base


class TimeSeries(Base):
    __tablename__ = "time_series"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    indicator = Column(String, nullable=False)
    geo_code = Column(String, nullable=False)
    period = Column(String, nullable=False)
    measure = Column(String, nullable=False)
    value = Column(Float)
    fetched_at = Column(String, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "source", "indicator", "geo_code", "period", "measure",
            name="uq_timeseries",
        ),
        Index("ix_ts_indicator_geo", "indicator", "geo_code"),
        Index("ix_ts_source_indicator", "source", "indicator"),
        Index("ix_ts_period", "period"),
    )


class Microdata(Base):
    __tablename__ = "microdata"

    id = Column(Integer, primary_key=True)
    quarter = Column(String, nullable=False)
    cuestionario = Column(Integer)
    isla = Column(String)
    aeropuerto = Column(String)
    sexo = Column(String)
    edad = Column(Integer)
    nacionalidad = Column(String)
    pais_residencia = Column(String)
    proposito = Column(String)
    noches = Column(Integer)
    aloj_categ = Column(String)
    gasto_euros = Column(Float)
    coste_vuelos_euros = Column(Float)
    coste_aloj_euros = Column(Float)
    satisfaccion = Column(String)
    cluster_id = Column(Integer)
    raw_json = Column(Text)

    __table_args__ = (
        UniqueConstraint("quarter", "cuestionario", name="uq_microdata"),
        Index("ix_micro_quarter", "quarter"),
        Index("ix_micro_cluster_id", "cluster_id"),
        Index("ix_micro_nacionalidad", "nacionalidad"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    model = Column(String, nullable=False)
    indicator = Column(String, nullable=False)
    geo_code = Column(String, nullable=False)
    period = Column(String, nullable=False)
    value_predicted = Column(Float)
    ci_lower_80 = Column(Float)
    ci_upper_80 = Column(Float)
    ci_lower_95 = Column(Float)
    ci_upper_95 = Column(Float)
    generated_at = Column(String, server_default=func.now())
    trained_at = Column(DateTime, default=func.now(), server_default=func.now())
    version = Column(Integer, default=1, server_default="1")
    is_current = Column(Boolean, default=True, server_default="1")

    __table_args__ = (
        Index("ix_pred_model_indicator_geo", "model", "indicator", "geo_code"),
        Index("ix_pred_period", "period"),
        Index("ix_pred_is_current", "is_current"),
    )


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    cluster_id = Column(Integer, nullable=False)
    cluster_name = Column(String)
    size_pct = Column(Float)
    avg_age = Column(Float)
    avg_spend = Column(Float)
    avg_nights = Column(Float)
    top_nationalities = Column(Text)
    top_accommodations = Column(Text)
    top_activities = Column(Text)
    top_motivations = Column(Text)
    characteristics = Column(Text)
    generated_at = Column(String, server_default=func.now())

    __table_args__ = (
        Index("ix_profile_cluster_id", "cluster_id"),
    )


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True)
    model = Column(String, nullable=False)
    indicator = Column(String, nullable=False)
    geo_code = Column(String, nullable=False)
    rmse = Column(Float)
    mae = Column(Float)
    mape = Column(Float)
    test_size = Column(Integer)
    generated_at = Column(String, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("model", "indicator", "geo_code", name="uq_model_metric"),
        Index("ix_metric_model_indicator", "model", "indicator"),
    )


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(Integer, primary_key=True)
    trained_at = Column(String, server_default=func.now())
    data_up_to = Column(String)
    data_hash = Column(String)
    models_trained = Column(Text)
    status = Column(String, nullable=False)
    error_message = Column(Text)
    duration_seconds = Column(Float)

    __table_args__ = (
        Index("ix_training_runs_trained_at", "trained_at"),
    )


class SavedScenario(Base):
    __tablename__ = "saved_scenarios"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    occupancy_change_pct = Column(Float, default=0.0)
    adr_change_pct = Column(Float, default=0.0)
    foreign_ratio_change_pct = Column(Float, default=0.0)
    horizon = Column(Integer, default=12)
    result_json = Column(Text)  # JSON-serialized scenario result
    created_at = Column(String, server_default=func.now())

    __table_args__ = (
        Index("ix_saved_scenario_created", "created_at"),
    )


class TourismEvent(Base):
    __tablename__ = "tourism_events"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String)
    impact_estimate = Column(String)
    location = Column(String)
    source = Column(String)
    created_at = Column(String, server_default=func.now())

    __table_args__ = (
        Index("ix_event_dates", "start_date", "end_date"),
        Index("ix_event_category", "category"),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True)
    source = Column(String, nullable=False)
    job_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    records_added = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(String)
    finished_at = Column(String)

    __table_args__ = (
        Index("ix_pipeline_source_status", "source", "status"),
    )
