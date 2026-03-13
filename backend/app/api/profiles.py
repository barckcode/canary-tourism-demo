"""Tourist profile and segmentation endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Microdata, Profile

router = APIRouter()


def safe_json_loads(s, default=None):
    """Safely parse a JSON string, returning default on failure."""
    if default is None:
        default = []
    try:
        return json.loads(s) if s else default
    except (json.JSONDecodeError, ValueError):
        return default


@router.get("")
def get_profiles(db: Session = Depends(get_db)):
    """Return all tourist profile clusters."""
    profiles = db.query(Profile).order_by(Profile.cluster_id).all()
    return {
        "clusters": [
            {
                "id": p.cluster_id,
                "name": p.cluster_name,
                "size_pct": p.size_pct,
                "avg_age": p.avg_age,
                "avg_spend": p.avg_spend,
                "avg_nights": p.avg_nights,
                "top_nationalities": safe_json_loads(p.top_nationalities),
                "top_accommodations": safe_json_loads(p.top_accommodations),
            }
            for p in profiles
        ]
    }


@router.get("/nationalities")
def get_nationality_profiles(db: Session = Depends(get_db)):
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
            "nationality": r.nacionalidad,
            "count": r.count,
            "avg_spend": round(r.avg_spend, 2) if r.avg_spend else None,
            "avg_nights": round(r.avg_nights, 1) if r.avg_nights else None,
        }
        for r in results
    ]


@router.get("/flows")
def get_flows(db: Session = Depends(get_db)):
    """Return Sankey flow data: Country -> Zone -> Accommodation."""
    # Country -> Accommodation flows
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

    nodes_set = set()
    links = []
    for f in flows:
        src = f"country_{f.nacionalidad}"
        tgt = f"accom_{f.aloj_categ}"
        nodes_set.add(src)
        nodes_set.add(tgt)
        links.append({"source": src, "target": tgt, "value": f.count})

    nodes = [{"id": n, "label": n.split("_", 1)[1]} for n in sorted(nodes_set)]
    return {"nodes": nodes, "links": links}


@router.get("/{cluster_id}")
def get_profile_detail(
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

    return {
        "id": profile.cluster_id,
        "name": profile.cluster_name,
        "size_pct": profile.size_pct,
        "avg_age": profile.avg_age,
        "avg_spend": profile.avg_spend,
        "avg_nights": profile.avg_nights,
        "top_nationalities": safe_json_loads(profile.top_nationalities),
        "top_accommodations": safe_json_loads(profile.top_accommodations),
        "top_activities": safe_json_loads(profile.top_activities),
        "top_motivations": safe_json_loads(profile.top_motivations),
        "characteristics": characteristics,
    }
