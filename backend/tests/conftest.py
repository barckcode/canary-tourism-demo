"""Shared test fixtures with isolated in-memory database."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import (
    Microdata,
    ModelMetric,
    Prediction,
    Profile,
    TimeSeries,
    TrainingRun,
)
from app.main import app


# Create an in-memory SQLite engine for tests.
# StaticPool ensures all connections share the same in-memory database.
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def _seed_test_data(session: Session) -> None:
    """Populate the in-memory database with realistic test data."""

    # --- Time Series: turistas (monthly, 2020-01 to 2025-12) ---
    base_turistas = [
        350000, 380000, 420000, 450000, 480000, 500000,
        520000, 510000, 490000, 460000, 400000, 370000,
    ]
    for year in range(2020, 2026):
        for month_idx, base in enumerate(base_turistas):
            month = month_idx + 1
            # Add some year-over-year growth
            growth = 1.0 + (year - 2020) * 0.03
            value = round(base * growth)
            session.add(TimeSeries(
                source="istac",
                indicator="turistas",
                geo_code="ES709",
                period=f"{year}-{month:02d}",
                measure="ABSOLUTE",
                value=value,
            ))

    # --- Time Series: turistas_extranjeros (needed by ScenarioEngine) ---
    for year in range(2020, 2026):
        for month_idx, base in enumerate(base_turistas):
            month = month_idx + 1
            growth = 1.0 + (year - 2020) * 0.03
            # Foreign tourists are ~70% of total
            value = round(base * growth * 0.7)
            session.add(TimeSeries(
                source="istac",
                indicator="turistas_extranjeros",
                geo_code="ES709",
                period=f"{year}-{month:02d}",
                measure="ABSOLUTE",
                value=value,
            ))

    # --- Time Series: occupancy, ADR, RevPAR, avg_stay and others ---
    indicators_data = {
        "alojatur_habitaciones_ocupacion": 72.5,
        "alojatur_ingresos_habitacion": 85.0,
        "alojatur_ingresos": 62.0,
        "alojatur_estancias_medias": 7.2,
        "alojatur_ocupacion": 68.0,
        "alojatur_adr": 90.0,
        "alojatur_revpar": 65.0,
        "alojatur_pernoctaciones": 2500000.0,
        # Needed by ScenarioEngine
        "alojatur_plazas_ocupacion": 65.0,
        "alojatur_tarifa_adr": 88.0,
    }
    for ind, base_val in indicators_data.items():
        for year in range(2022, 2026):
            for month in range(1, 13):
                variation = 1.0 + (month - 6) * 0.01
                session.add(TimeSeries(
                    source="istac",
                    indicator=ind,
                    geo_code="ES709",
                    period=f"{year}-{month:02d}",
                    measure="ABSOLUTE",
                    value=round(base_val * variation, 2),
                ))

    # --- Time Series: hotel_pernoctaciones by municipality ---
    pernoctaciones_munis = {
        "hotel_pernoctaciones_adeje": ("ES709_ADEJE", 450000.0),
        "hotel_pernoctaciones_arona": ("ES709_ARONA", 380000.0),
        "hotel_pernoctaciones_puerto_cruz": ("ES709_PCRUZ", 200000.0),
    }
    for ind, (geo, base_val) in pernoctaciones_munis.items():
        for year in range(2024, 2026):
            for month in range(1, 13):
                variation = 1.0 + (month - 6) * 0.02
                session.add(TimeSeries(
                    source="ine",
                    indicator=ind,
                    geo_code=geo,
                    period=f"{year}-{month:02d}",
                    measure="ABSOLUTE",
                    value=round(base_val * variation),
                ))

    # --- Predictions: ensemble, sarima, holt_winters, seasonal_naive ---
    for model_name in ["ensemble", "sarima", "holt_winters", "seasonal_naive"]:
        for i in range(1, 13):
            period = f"2026-{i:02d}"
            base = 450000 + i * 10000
            session.add(Prediction(
                model=model_name,
                indicator="turistas",
                geo_code="ES709",
                period=period,
                value_predicted=base,
                ci_lower_80=base * 0.92,
                ci_upper_80=base * 1.08,
                ci_lower_95=base * 0.85,
                ci_upper_95=base * 1.15,
            ))

    # --- Model Metrics ---
    for model_name in ["ensemble", "sarima", "holt_winters", "seasonal_naive"]:
        mape = {"ensemble": 5.2, "sarima": 7.1, "holt_winters": 6.8, "seasonal_naive": 9.5}
        session.add(ModelMetric(
            model=model_name,
            indicator="turistas",
            geo_code="ES709",
            rmse=25000.0,
            mae=18000.0,
            mape=mape[model_name],
            test_size=12,
        ))

    # --- Profiles: 4 clusters ---
    cluster_data = [
        ("Budget Travelers", 0.35, 32.0, 850.0, 7.0,
         ["826", "276"], ["HOTEL_ESTRELLAS_S1", "APARTAMENTO_VILLA"],
         ["Beach", "Hiking"], ["Relaxation", "Nature"]),
        ("Luxury Seekers", 0.20, 48.0, 2200.0, 10.0,
         ["276", "826"], ["HOTEL_ESTRELLAS_5", "HOTEL_ESTRELLAS_4"],
         ["Spa", "Golf", "Fine Dining"], ["Luxury", "Wellness"]),
        ("Family Vacationers", 0.30, 42.0, 1500.0, 8.0,
         ["826", "250"], ["HOTEL_ESTRELLAS_4", "APARTAMENTO_VILLA"],
         ["Theme Parks", "Beach"], ["Family", "Entertainment"]),
        ("Adventure Enthusiasts", 0.15, 28.0, 1100.0, 6.0,
         ["528", "276"], ["VIVIENDA_HABITACION_ALQUILADA_PARTICULAR"],
         ["Hiking", "Surfing", "Diving"], ["Adventure", "Sports"]),
    ]
    for idx, (name, size, age, spend, nights, nats, accoms, acts, motivs) in enumerate(cluster_data):
        chars = {
            "avg_satisfaction": 7.5 + idx * 0.3,
            "spending_breakdown": {
                "accommodation": 40 + idx * 2,
                "food": 25 - idx,
                "transport": 15,
                "activities": 20 - idx,
            },
        }
        session.add(Profile(
            cluster_id=idx,
            cluster_name=name,
            size_pct=size * 100,
            avg_age=age,
            avg_spend=spend,
            avg_nights=nights,
            top_nationalities=json.dumps(nats),
            top_accommodations=json.dumps(accoms),
            top_activities=json.dumps(acts),
            top_motivations=json.dumps(motivs),
            characteristics=json.dumps(chars),
        ))

    # --- Microdata: representative tourist records ---
    nationalities = ["826", "276", "250", "380", "528"]
    accommodations = [
        "HOTEL_ESTRELLAS_4", "HOTEL_ESTRELLAS_5",
        "APARTAMENTO_VILLA", "VIVIENDA_HABITACION_ALQUILADA_PARTICULAR",
    ]
    purposes = ["OCIO", "NEGOCIOS", "VISITA_FAMILIARES", "OCIO", "OCIO"]
    importance_levels = ["NADA", "ALGO", "BASTANTE", "MUCHO"]
    activity_cols = [
        "ACTIV_PLAYA", "ACTIV_PISCINA", "ACTIV_PASEAR", "ACTIV_ISLA",
        "ACTIV_EXCURS_ORGANIZ", "ACTIV_EXCURS_MAR", "ACTIV_ASTRONOMIA",
        "ACTIV_MUSEOS", "ACTIV_GASTRONOMIA_CANARIA", "ACTIV_PARQUES_OCIO",
        "ACTIV_OCIO", "ACTIV_BELLEZA", "ACTIV_SENDERISMO",
        "ACTIV_OTRAS_NATURALEZA", "ACTIV_BUCEO", "ACTIV_NADAR",
        "ACTIV_SURF", "ACTIV_CICLISMO", "ACTIV_GOLF",
    ]
    importance_cols = [
        "IMPORTANCIA_CLIMA", "IMPORTANCIA_PLAYAS", "IMPORTANCIA_MAR",
        "IMPORTANCIA_PAISAJES", "IMPORTANCIA_ENTORNO_AMBIENTAL",
        "IMPORTANCIA_RED_SENDEROS", "IMPORTANCIA_OFERTA_ALOJATIVA",
        "IMPORTANCIA_PATRIMONIO_HISTORICO", "IMPORTANCIA_OFERTA_CULTURAL",
        "IMPORTANCIA_DIVERSION", "IMPORTANCIA_OCIO_NOCTURNO",
        "IMPORTANCIA_OFERTA_COMERCIAL", "IMPORTANCIA_GASTRONOMIA",
        "IMPORTANCIA_VIAJE_SENCILLO", "IMPORTANCIA_SEGURIDAD",
        "IMPORTANCIA_TRANQUILIDAD", "IMPORTANCIA_PRECIO",
        "IMPORTANCIA_EXOTISMO", "IMPORTANCIA_AUTENTICIDAD",
    ]

    import random
    rng = random.Random(42)

    cuestionario = 1
    for quarter in ["2024Q1", "2024Q2", "2024Q3", "2024Q4"]:
        for nat_idx, nat in enumerate(nationalities):
            # Create enough records per nationality/accommodation to pass the
            # flows endpoint >= 10 threshold
            for _ in range(12):
                accom = accommodations[nat_idx % len(accommodations)]
                edad = 25 + rng.randint(0, 40)
                gasto = 500.0 + rng.random() * 2000
                noches = 4 + rng.randint(0, 10)
                satisfaccion = str(rng.randint(5, 10))

                raw = {
                    "NUMERO_CUESTIONARIO": cuestionario,
                    "ISLA": "ES709",
                    "NACIONALIDAD": nat,
                    "PAIS_RESIDENCIA": nat,
                    "SEXO": "M" if cuestionario % 2 == 0 else "F",
                    "EDAD": edad,
                    "PROPOSITO": purposes[nat_idx],
                    "NOCHES": noches,
                    "ALOJ_CATEG": accom,
                    "GASTO_EUROS": round(gasto, 2),
                    "COSTE_VUELOS_EUROS": round(200.0 + rng.random() * 400, 2),
                    "COSTE_ALOJ_EUROS": round(300.0 + rng.random() * 600, 2),
                    "SATISFACCION": satisfaccion,
                    "PERSONAS_TOTAL": rng.randint(1, 5),
                    "DESGLOSE_RESTAURANT": round(50 + rng.random() * 200, 2),
                    "DESGLOSE_EXCURS_ORGANIZ": round(20 + rng.random() * 150, 2),
                    "DESGLOSE_ALQ_VEHIC": round(30 + rng.random() * 200, 2),
                    "DESGLOSE_ALIM_SUPER": round(20 + rng.random() * 100, 2),
                    "DESGLOSE_DEPORTES": round(rng.random() * 80, 2),
                    "DESGLOSE_PARQUES_OCIO": round(rng.random() * 60, 2),
                    "DESGLOSE_SOUVENIRS": round(rng.random() * 50, 2),
                    "DESGLOSE_EXTRA_ALOJ": round(rng.random() * 80, 2),
                }

                # Add activity columns with variation
                for act in activity_cols:
                    raw[act] = 1 if rng.random() > 0.5 else 6

                # Add importance columns with variation
                for imp in importance_cols:
                    raw[imp] = rng.choice(importance_levels)

                session.add(Microdata(
                    quarter=quarter,
                    cuestionario=cuestionario,
                    isla="ES709",
                    aeropuerto="TFS",
                    sexo=raw["SEXO"],
                    edad=edad,
                    nacionalidad=nat,
                    pais_residencia=nat,
                    proposito=raw["PROPOSITO"],
                    noches=noches,
                    aloj_categ=accom,
                    gasto_euros=raw["GASTO_EUROS"],
                    coste_vuelos_euros=raw["COSTE_VUELOS_EUROS"],
                    coste_aloj_euros=raw["COSTE_ALOJ_EUROS"],
                    satisfaccion=satisfaccion,
                    cluster_id=nat_idx % 4,
                    raw_json=json.dumps(raw),
                ))
                cuestionario += 1

    session.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all tables in the in-memory database and seed test data."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        _seed_test_data(session)
    finally:
        session.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db(setup_test_db):
    """Provide an isolated database session for tests."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _override_get_db():
    """Dependency override that provides the test database session."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(setup_test_db):
    """Provide a FastAPI test client using the in-memory test database."""
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
