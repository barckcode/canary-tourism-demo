"""Data seeding script — loads raw data files into SQLite.

Reads CSV/JSON files from the raw data directory and populates
the time_series and microdata tables. Idempotent via INSERT OR REPLACE.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Microdata, TimeSeries

logger = logging.getLogger(__name__)

# INE FK_Periodo → month number (monthly series)
INE_MONTHLY_PERIOD = {i: i for i in range(1, 13)}

# INE FK_Periodo → quarter label (quarterly series)
INE_QUARTERLY_PERIOD = {19: "Q1", 20: "Q2", 21: "Q3", 22: "Q4"}

# Microdata columns to extract into typed fields
MICRODATA_KEY_COLS = {
    "NUMERO_CUESTIONARIO": "cuestionario",
    "ISLA": "isla",
    "AEROPUERTO_ORIGEN": "aeropuerto",
    "SEXO": "sexo",
    "EDAD": "edad",
    "NACIONALIDAD": "nacionalidad",
    "PAIS_RESIDENCIA": "pais_residencia",
    "PROPOSITO": "proposito",
    "NOCHES": "noches",
    "ALOJ_CATEG": "aloj_categ",
    "GASTO_EUROS": "gasto_euros",
    "COSTE_VUELOS_EUROS": "coste_vuelos_euros",
    "COSTE_ALOJ_EUROS": "coste_aloj_euros",
    "SATISFACCION": "satisfaccion",
}

PLACEHOLDER_CODES = {"_Z", "_U", "_N", "_Y", ""}


def _safe_int(val: str) -> int | None:
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val: str) -> float | None:
    if val in PLACEHOLDER_CODES:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def seed_istac_timeseries(db: Session, data_dir: Path) -> int:
    """Load ISTAC *_tenerife.csv files into time_series table."""
    istac_dir = data_dir / "istac"
    count = 0

    for csv_path in sorted(istac_dir.glob("*_tenerife.csv")):
        indicator_name = csv_path.stem.replace("_tenerife", "").lower()
        logger.info("Loading ISTAC: %s", csv_path.name)

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = _safe_float(row.get("value", ""))
                if value is None:
                    continue

                db.execute(
                    text("""
                        INSERT OR REPLACE INTO time_series
                            (source, indicator, geo_code, period, measure, value)
                        VALUES (:source, :indicator, :geo_code, :period, :measure, :value)
                    """),
                    {
                        "source": "istac",
                        "indicator": row.get("indicator", indicator_name).lower(),
                        "geo_code": row.get("geo_code", "ES709"),
                        "period": row.get("time", ""),
                        "measure": row.get("measure", "ABSOLUTE"),
                        "value": value,
                    },
                )
                count += 1

    db.commit()
    logger.info("ISTAC time series: %d records loaded.", count)
    return count


def seed_ine_timeseries(db: Session, data_dir: Path) -> int:
    """Load INE JSON files into time_series table."""
    ine_dir = data_dir / "ine"
    count = 0

    for json_path in sorted(ine_dir.glob("*.json")):
        if "summary" in json_path.name:
            continue

        logger.info("Loading INE: %s", json_path.name)
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        for series_id, series_info in data.items():
            description = series_info.get("description", series_id)
            indicator = (
                description.lower()
                .replace(".", "")
                .replace(" ", "_")[:100]
            )

            for rec in series_info.get("records", []):
                valor = rec.get("Valor")
                if valor is None:
                    continue

                anyo = rec["Anyo"]
                fk_periodo = rec["FK_Periodo"]

                # Determine period format
                if fk_periodo in INE_QUARTERLY_PERIOD:
                    period = f"{anyo}-{INE_QUARTERLY_PERIOD[fk_periodo]}"
                elif 1 <= fk_periodo <= 12:
                    period = f"{anyo}-{fk_periodo:02d}"
                else:
                    continue

                db.execute(
                    text("""
                        INSERT OR REPLACE INTO time_series
                            (source, indicator, geo_code, period, measure, value)
                        VALUES (:source, :indicator, :geo_code, :period, :measure, :value)
                    """),
                    {
                        "source": "ine",
                        "indicator": indicator,
                        "geo_code": "ES709",
                        "period": period,
                        "measure": "ABSOLUTE",
                        "value": float(valor),
                    },
                )
                count += 1

    db.commit()
    logger.info("INE time series: %d records loaded.", count)
    return count


def seed_microdata(db: Session, data_dir: Path) -> int:
    """Load EGT microdata CSVs into microdata table."""
    micro_dir = data_dir / "cabildo" / "istac_extra"
    count = 0

    for csv_path in sorted(micro_dir.glob("microdatos_gasto_turistico_*.csv")):
        # Extract quarter from filename: microdatos_gasto_turistico_2024q3.csv -> 2024Q3
        quarter = csv_path.stem.split("_")[-1].upper()
        logger.info("Loading microdata: %s (quarter=%s)", csv_path.name, quarter)

        with open(csv_path, encoding="latin-1") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Filter to Tenerife only (ES709)
                isla = row.get("ISLA", "")
                if isla != "ES709":
                    continue

                cuestionario = _safe_int(row.get("NUMERO_CUESTIONARIO", ""))
                if cuestionario is None:
                    continue

                record = {
                    "quarter": quarter,
                    "cuestionario": cuestionario,
                    "isla": row.get("ISLA", "") or None,
                    "aeropuerto": row.get("AEROPUERTO_ORIGEN", "") or None,
                    "sexo": row.get("SEXO", "") or None,
                    "edad": _safe_int(row.get("EDAD", "")),
                    "nacionalidad": row.get("NACIONALIDAD", "") or None,
                    "pais_residencia": row.get("PAIS_RESIDENCIA", "") or None,
                    "proposito": row.get("PROPOSITO", "") or None,
                    "noches": _safe_int(row.get("NOCHES", "")),
                    "aloj_categ": row.get("ALOJ_CATEG", "") or None,
                    "gasto_euros": _safe_float(row.get("GASTO_EUROS", "")),
                    "coste_vuelos_euros": _safe_float(
                        row.get("COSTE_VUELOS_EUROS", "")
                    ),
                    "coste_aloj_euros": _safe_float(
                        row.get("COSTE_ALOJ_EUROS", "")
                    ),
                    "satisfaccion": row.get("SATISFACCION", "") or None,
                    "raw_json": json.dumps(
                        {k: v for k, v in row.items() if v not in PLACEHOLDER_CODES},
                        ensure_ascii=False,
                    ),
                }

                # Clean placeholder values
                for key in ["isla", "aeropuerto", "sexo", "nacionalidad",
                            "pais_residencia", "proposito", "aloj_categ",
                            "satisfaccion"]:
                    if record[key] in PLACEHOLDER_CODES:
                        record[key] = None

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
                    record,
                )
                count += 1

        # Commit after each file to avoid huge transactions
        db.commit()

    logger.info("Microdata: %d records loaded.", count)
    return count


def seed_spending_profiles(db: Session, data_dir: Path) -> int:
    """Load ISTAC spending/profile CSVs from cabildo/istac_extra."""
    extra_dir = data_dir / "cabildo" / "istac_extra"
    count = 0

    for csv_path in sorted(extra_dir.glob("*.csv")):
        if "microdatos" in csv_path.name:
            continue

        logger.info("Loading spending/profile: %s", csv_path.name)
        indicator = csv_path.stem.lower()

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # These CSVs use SDMX-style headers
            obs_col = "OBS_VALUE" if "OBS_VALUE" in headers else None
            period_col = (
                "TIME_PERIOD_CODE"
                if "TIME_PERIOD_CODE" in headers
                else None
            )
            measure_col = (
                "MEDIDAS_CODE" if "MEDIDAS_CODE" in headers else None
            )
            territory_col = (
                "TERRITORIO_CODE" if "TERRITORIO_CODE" in headers else None
            )

            if not obs_col or not period_col:
                logger.warning("Skipping %s — unknown format", csv_path.name)
                continue

            for row in reader:
                value = _safe_float(row.get(obs_col, ""))
                if value is None:
                    continue

                period_raw = row.get(period_col, "")
                geo = row.get(territory_col, "ES70")
                measure = row.get(measure_col, "ABSOLUTE")

                db.execute(
                    text("""
                        INSERT OR REPLACE INTO time_series
                            (source, indicator, geo_code, period, measure, value)
                        VALUES (:source, :indicator, :geo_code, :period,
                                :measure, :value)
                    """),
                    {
                        "source": "istac",
                        "indicator": indicator,
                        "geo_code": geo,
                        "period": period_raw,
                        "measure": measure,
                        "value": value,
                    },
                )
                count += 1

    db.commit()
    logger.info("Spending/profile data: %d records loaded.", count)
    return count


def seed_all(db: Session):
    """Seed all data from raw files into the database."""
    data_dir = settings.raw_data_dir
    logger.info("Starting data seed from %s", data_dir)

    total = 0
    total += seed_istac_timeseries(db, data_dir)
    total += seed_ine_timeseries(db, data_dir)
    total += seed_microdata(db, data_dir)
    total += seed_spending_profiles(db, data_dir)

    logger.info("Data seeding complete. Total records: %d", total)
    return total
