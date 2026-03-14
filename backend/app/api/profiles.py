"""Tourist profile and segmentation endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Microdata, Profile
from app.rate_limit import limiter

router = APIRouter()


def safe_json_loads(s, default=None):
    """Safely parse a JSON string, returning default on failure."""
    if default is None:
        default = []
    try:
        return json.loads(s) if s else default
    except (json.JSONDecodeError, ValueError):
        return default


# EGT/ISTAC nationality codes → human-readable names
NATIONALITY_LABELS = {
    "826": "United Kingdom",
    "276": "Germany",
    "250": "France",
    "380": "Italy",
    "724_XES70": "Spain (mainland)",
    "528": "Netherlands",
    "372": "Ireland",
    "056": "Belgium",
    "756": "Switzerland",
    "154_L1": "Nordic Countries",
    "001_O": "Other",
    "840": "United States",
    "616": "Poland",
    "203": "Czech Republic",
    "620": "Portugal",
    "040": "Austria",
    "643": "Russia",
    "752": "Sweden",
    "246": "Finland",
    "208": "Denmark",
    "578": "Norway",
}

ACCOMMODATION_LABELS = {
    "HOTEL_ESTRELLAS_4": "4-Star Hotel",
    "HOTEL_ESTRELLAS_5": "5-Star Hotel",
    "HOTEL_ESTRELLAS_S1": "1-3 Star Hotel",
    "APARTAMENTO_VILLA": "Apartment / Villa",
    "VIVIENDA_HABITACION_ALQUILADA_PARTICULAR": "Private Rental",
    "VIVIENDA_GRATUITA": "Friends & Family",
    "_O": "Other",
}


@router.get("")
@limiter.limit("60/minute")
def get_profiles(request: Request, db: Session = Depends(get_db)):
    """Return all tourist profile clusters."""
    profiles = db.query(Profile).order_by(Profile.cluster_id).all()
    clusters = []
    for p in profiles:
        characteristics = safe_json_loads(p.characteristics, default={})
        if isinstance(characteristics, list):
            characteristics = {}

        # Convert nationality codes to labeled objects
        raw_nationalities = safe_json_loads(p.top_nationalities)
        nat_entries = [
            {"nationality": NATIONALITY_LABELS.get(code, code), "percentage": 0}
            for code in raw_nationalities
        ] if isinstance(raw_nationalities, list) else []

        # Convert accommodation codes to labeled objects
        raw_accommodations = safe_json_loads(p.top_accommodations)
        acc_entries = [
            {"type": ACCOMMODATION_LABELS.get(code, code), "percentage": 0}
            for code in raw_accommodations
        ] if isinstance(raw_accommodations, list) else []

        clusters.append({
            "id": p.cluster_id,
            "name": p.cluster_name,
            "size_pct": p.size_pct,
            "avg_age": p.avg_age,
            "avg_spend": p.avg_spend,
            "avg_nights": p.avg_nights,
            "top_nationalities": nat_entries,
            "top_accommodations": acc_entries,
            "top_activities": safe_json_loads(p.top_activities),
            "top_motivations": safe_json_loads(p.top_motivations),
            "avg_satisfaction": characteristics.get("avg_satisfaction"),
            "spending_breakdown": characteristics.get("spending_breakdown", {}),
        })
    return {"clusters": clusters}


@router.get("/nationalities")
@limiter.limit("60/minute")
def get_nationality_profiles(request: Request, db: Session = Depends(get_db)):
    """Return aggregate stats by nationality from microdata."""
    results = (
        db.query(
            Microdata.nacionalidad,
            func.count(Microdata.id).label("count"),
            func.avg(Microdata.gasto_euros).label("avg_spend"),
            func.avg(Microdata.noches).label("avg_nights"),
        )
        .filter(Microdata.nacionalidad.isnot(None))
        .group_by(Microdata.nacionalidad)
        .order_by(func.count(Microdata.id).desc())
        .all()
    )
    return [
        {
            "nationality": NATIONALITY_LABELS.get(r.nacionalidad, r.nacionalidad),
            "count": r.count,
            "avg_spend": round(r.avg_spend, 2) if r.avg_spend else None,
            "avg_nights": round(r.avg_nights, 1) if r.avg_nights else None,
        }
        for r in results
    ]


@router.get("/flows")
@limiter.limit("60/minute")
def get_flows(request: Request, db: Session = Depends(get_db)):
    """Return Sankey flow data: Country -> Accommodation type."""
    flows = (
        db.query(
            Microdata.nacionalidad,
            Microdata.aloj_categ,
            func.count(Microdata.id).label("count"),
        )
        .filter(
            Microdata.nacionalidad.isnot(None),
            Microdata.aloj_categ.isnot(None),
        )
        .group_by(Microdata.nacionalidad, Microdata.aloj_categ)
        .having(func.count(Microdata.id) >= 10)
        .all()
    )

    # Aggregate totals per country to find top 6
    country_totals: dict[str, int] = {}
    for f in flows:
        country_totals[f.nacionalidad] = country_totals.get(f.nacionalidad, 0) + f.count
    top_countries = sorted(country_totals, key=country_totals.get, reverse=True)[:6]

    # Aggregate totals per accommodation to find top 4
    accom_totals: dict[str, int] = {}
    for f in flows:
        accom_totals[f.aloj_categ] = accom_totals.get(f.aloj_categ, 0) + f.count
    top_accoms = sorted(accom_totals, key=accom_totals.get, reverse=True)[:4]

    # Build filtered flows with "Other" grouping
    filtered: dict[tuple[str, str], int] = {}
    for f in flows:
        if f.nacionalidad not in top_countries:
            continue
        accom = f.aloj_categ if f.aloj_categ in top_accoms else "_O"
        key = (f.nacionalidad, accom)
        filtered[key] = filtered.get(key, 0) + f.count

    nodes_set = set()
    links = []
    for (nat, accom), count in filtered.items():
        src = f"country_{nat}"
        tgt = f"accom_{accom}"
        nodes_set.add(src)
        nodes_set.add(tgt)
        links.append({"source": src, "target": tgt, "value": count})

    nodes = []
    for n in sorted(nodes_set):
        if n.startswith("country_"):
            code = n.split("_", 1)[1]
            label = NATIONALITY_LABELS.get(code, code)
        else:
            code = n.split("_", 1)[1]
            label = ACCOMMODATION_LABELS.get(code, code)
        nodes.append({"id": n, "label": label})

    return {"nodes": nodes, "links": links}


@router.get("/spending")
@limiter.limit("60/minute")
def get_spending_by_cluster(request: Request, db: Session = Depends(get_db)):
    """Return real spending breakdown per cluster computed from microdata.

    Aggregates spending category columns (DESGLOSE_*) from the raw_json
    of each microdata record, grouped by assigned cluster_id.
    """
    rows = (
        db.query(Microdata.cluster_id, Microdata.raw_json)
        .filter(Microdata.cluster_id.isnot(None), Microdata.raw_json.isnot(None))
        .all()
    )

    if not rows:
        return {"spending_by_cluster": {}}

    SPENDING_COLS = [
        "DESGLOSE_RESTAURANT",
        "DESGLOSE_EXCURS_ORGANIZ",
        "DESGLOSE_ALQ_VEHIC",
        "DESGLOSE_ALIM_SUPER",
        "DESGLOSE_DEPORTES",
        "DESGLOSE_PARQUES_OCIO",
        "DESGLOSE_SOUVENIRS",
        "DESGLOSE_EXTRA_ALOJ",
    ]

    from collections import defaultdict

    cluster_sums: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for cid, raw in rows:
        try:
            data = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            continue

        for col in SPENDING_COLS:
            val = data.get(col)
            if val is not None and val not in ("_Z", "_U", "_N", ""):
                try:
                    cluster_sums[cid][col].append(float(val))
                except (ValueError, TypeError):
                    continue

    result: dict[int, list[dict]] = {}
    for cid in sorted(cluster_sums.keys()):
        categories = []
        total_avg = 0.0
        for col in SPENDING_COLS:
            vals = cluster_sums[cid].get(col, [])
            avg = sum(vals) / len(vals) if vals else 0.0
            total_avg += avg
            name = col.replace("DESGLOSE_", "").replace("_", " ").title()
            categories.append({"category": name, "amount": round(avg, 2)})

        # Calculate percentages
        for cat in categories:
            cat["pct"] = (
                round(cat["amount"] / total_avg * 100, 1) if total_avg > 0 else 0
            )

        # Sort by amount descending and filter out zero-amount categories
        categories = [c for c in categories if c["amount"] > 0]
        categories.sort(key=lambda x: x["amount"], reverse=True)
        result[cid] = categories

    return {"spending_by_cluster": result}


@router.get("/{cluster_id}")
@limiter.limit("60/minute")
def get_profile_detail(
    request: Request,
    cluster_id: int = Path(..., description="Cluster ID"),
    db: Session = Depends(get_db),
):
    """Return detailed profile for a specific cluster."""
    profile = (
        db.query(Profile).filter(Profile.cluster_id == cluster_id).first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Cluster not found")

    characteristics = safe_json_loads(profile.characteristics, default={})
    if isinstance(characteristics, list):
        characteristics = {}

    # Convert nationality codes to labeled objects
    raw_nationalities = safe_json_loads(profile.top_nationalities)
    nat_entries = [
        {"nationality": NATIONALITY_LABELS.get(code, code), "percentage": 0}
        for code in raw_nationalities
    ] if isinstance(raw_nationalities, list) else []

    # Convert accommodation codes to labeled objects
    raw_accommodations = safe_json_loads(profile.top_accommodations)
    acc_entries = [
        {"type": ACCOMMODATION_LABELS.get(code, code), "percentage": 0}
        for code in raw_accommodations
    ] if isinstance(raw_accommodations, list) else []

    return {
        "id": profile.cluster_id,
        "name": profile.cluster_name,
        "size_pct": profile.size_pct,
        "avg_age": profile.avg_age,
        "avg_spend": profile.avg_spend,
        "avg_nights": profile.avg_nights,
        "top_nationalities": nat_entries,
        "top_accommodations": acc_entries,
        "top_activities": safe_json_loads(profile.top_activities),
        "top_motivations": safe_json_loads(profile.top_motivations),
        "avg_satisfaction": characteristics.get("avg_satisfaction"),
        "spending_breakdown": characteristics.get("spending_breakdown", {}),
        "characteristics": characteristics,
    }
