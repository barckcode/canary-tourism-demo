"""K-Means tourist profiler.

Clusters tourists from EGT microdata into segments based on
demographics, spending, accommodation, and behavioral features.
"""

import json
import logging
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Ordinal mapping for IMPORTANCIA columns
IMPORTANCE_MAP = {"NADA": 0, "ALGO": 1, "BASTANTE": 2, "MUCHO": 3}

# Ordinal mapping for SATISFACCION
SATISFACTION_MAP = {str(i): i for i in range(11)}  # 0-10

# Activity columns (binary: 1=yes, 6=no)
ACTIVITY_COLS = [
    "ACTIV_PLAYA", "ACTIV_PISCINA", "ACTIV_PASEAR", "ACTIV_ISLA",
    "ACTIV_EXCURS_ORGANIZ", "ACTIV_EXCURS_MAR", "ACTIV_ASTRONOMIA",
    "ACTIV_MUSEOS", "ACTIV_GASTRONOMIA_CANARIA", "ACTIV_PARQUES_OCIO",
    "ACTIV_OCIO", "ACTIV_BELLEZA", "ACTIV_SENDERISMO",
    "ACTIV_OTRAS_NATURALEZA", "ACTIV_BUCEO", "ACTIV_NADAR",
    "ACTIV_SURF", "ACTIV_CICLISMO", "ACTIV_GOLF",
]

IMPORTANCE_COLS = [
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

CLUSTER_NAMES = {
    0: "Budget / Young / Short-stay",
    1: "High-spend / Family",
    2: "Budget / Older / Medium-stay",
    3: "Premium / Long-stay",
}


class TouristProfiler:
    """K-Means clustering engine for tourist segmentation."""

    def __init__(self, n_clusters: int = 4):
        self.n_clusters = n_clusters
        self.model = None
        self.scaler = None
        self.is_fitted = False
        self.feature_names = []
        self.raw_df = None
        self.labels = None

    def _parse_raw_records(self, raw_jsons: list[str]) -> pd.DataFrame:
        """Parse raw_json strings into a DataFrame with profiling features."""
        records = [json.loads(r) for r in raw_jsons]
        df = pd.DataFrame(records)

        features = pd.DataFrame(index=df.index)

        # Numeric features
        for col in ["EDAD", "GASTO_EUROS", "NOCHES", "COSTE_VUELOS_EUROS",
                     "COSTE_ALOJ_EUROS", "PERSONAS_TOTAL"]:
            features[col] = pd.to_numeric(df.get(col, pd.Series(dtype=float)),
                                          errors="coerce")

        # Ordinal: importance columns
        for col in IMPORTANCE_COLS:
            features[col] = df.get(col, pd.Series(dtype=str)).map(IMPORTANCE_MAP)

        # Binary: activity columns (1=did, 6=didn't → 1/0)
        for col in ACTIVITY_COLS:
            vals = pd.to_numeric(df.get(col, pd.Series(dtype=float)), errors="coerce")
            features[col] = (vals == 1).astype(float)

        # Satisfaction (0-10 ordinal)
        features["SATISFACCION"] = pd.to_numeric(
            df.get("SATISFACCION", pd.Series(dtype=float)), errors="coerce"
        )

        # Top categorical features (one-hot top-N for clustering)
        for col, top_n in [("NACIONALIDAD", 10), ("PROPOSITO", 5), ("ALOJ_CATEG", 6)]:
            vals = df.get(col, pd.Series(dtype=str))
            top_vals = vals.value_counts().head(top_n).index.tolist()
            for v in top_vals:
                features[f"{col}_{v}"] = (vals == v).astype(float)

        return features, df

    def fit(self, raw_jsons: list[str]) -> np.ndarray:
        """Train K-Means on preprocessed microdata features.

        Args:
            raw_jsons: List of raw_json strings from microdata table.

        Returns:
            Cluster labels array.
        """
        features, raw_df = self._parse_raw_records(raw_jsons)
        self.raw_df = raw_df
        self.feature_names = features.columns.tolist()

        # Fill NaN with median for numeric, 0 for binary/ordinal
        features = features.fillna(features.median())

        # Scale
        self.scaler = StandardScaler()
        X = self.scaler.fit_transform(features)

        # K-Means
        logger.info("Fitting K-Means with K=%d on %d records, %d features.",
                     self.n_clusters, X.shape[0], X.shape[1])
        self.model = KMeans(
            n_clusters=self.n_clusters,
            n_init=10,
            max_iter=300,
            random_state=42,
        )
        self.labels = self.model.fit_predict(X)
        self.is_fitted = True

        # Log cluster sizes
        unique, counts = np.unique(self.labels, return_counts=True)
        for c, n in zip(unique, counts):
            logger.info("Cluster %d: %d records (%.1f%%)",
                        c, n, n / len(self.labels) * 100)

        return self.labels

    def get_profiles(self) -> list[dict]:
        """Return cluster profile summaries."""
        if not self.is_fitted:
            raise RuntimeError("Profiler not fitted.")

        profiles = []
        total = len(self.labels)

        for cluster_id in range(self.n_clusters):
            mask = self.labels == cluster_id
            cluster_df = self.raw_df[mask]
            size = mask.sum()

            # Numeric averages
            avg_age = pd.to_numeric(cluster_df.get("EDAD"), errors="coerce").mean()
            avg_spend = pd.to_numeric(cluster_df.get("GASTO_EUROS"), errors="coerce").mean()
            avg_nights = pd.to_numeric(cluster_df.get("NOCHES"), errors="coerce").mean()

            # Top nationalities
            nat_counts = Counter(
                v for v in cluster_df.get("NACIONALIDAD", []) if v and v not in ("_Z", "_U", "_N")
            )
            top_nat = [k for k, _ in nat_counts.most_common(5)]

            # Top accommodations
            acc_counts = Counter(
                v for v in cluster_df.get("ALOJ_CATEG", []) if v and v not in ("_Z", "_U", "_N")
            )
            top_acc = [k for k, _ in acc_counts.most_common(5)]

            # Top activities (columns where > 30% of cluster did it)
            top_activities = []
            for col in ACTIVITY_COLS:
                vals = pd.to_numeric(cluster_df.get(col), errors="coerce")
                pct = (vals == 1).mean()
                if pct > 0.3:
                    activity_name = col.replace("ACTIV_", "").replace("_", " ").title()
                    top_activities.append(activity_name)

            # Top motivations (highest average importance)
            motivation_scores = {}
            for col in IMPORTANCE_COLS:
                vals = cluster_df.get(col, pd.Series(dtype=str)).map(IMPORTANCE_MAP)
                mean_score = vals.mean()
                if not np.isnan(mean_score):
                    name = col.replace("IMPORTANCIA_", "").replace("_", " ").title()
                    motivation_scores[name] = mean_score
            top_motivations = sorted(motivation_scores, key=motivation_scores.get,
                                     reverse=True)[:5]

            # Spending breakdown
            spending = {}
            for col in ["DESGLOSE_RESTAURANT", "DESGLOSE_EXCURS_ORGANIZ",
                         "DESGLOSE_ALQ_VEHIC", "DESGLOSE_ALIM_SUPER",
                         "DESGLOSE_DEPORTES", "DESGLOSE_PARQUES_OCIO",
                         "DESGLOSE_SOUVENIRS", "DESGLOSE_EXTRA_ALOJ"]:
                vals = pd.to_numeric(cluster_df.get(col), errors="coerce")
                mean_val = vals.mean()
                if not np.isnan(mean_val):
                    name = col.replace("DESGLOSE_", "").replace("_", " ").title()
                    spending[name] = round(mean_val, 2)

            # Purpose distribution
            purpose_counts = Counter(
                v for v in cluster_df.get("PROPOSITO", []) if v and v not in ("_Z", "_U", "_N")
            )
            top_purpose = purpose_counts.most_common(1)[0][0] if purpose_counts else None

            characteristics = {
                "purpose": top_purpose,
                "spending_breakdown": spending,
                "avg_satisfaction": float(
                    pd.to_numeric(cluster_df.get("SATISFACCION"), errors="coerce").mean()
                ) if "SATISFACCION" in cluster_df.columns else None,
                "avg_personas": float(
                    pd.to_numeric(cluster_df.get("PERSONAS_TOTAL"), errors="coerce").mean()
                ) if "PERSONAS_TOTAL" in cluster_df.columns else None,
            }

            # Assign meaningful name based on ordering
            name = CLUSTER_NAMES.get(cluster_id, f"Cluster {cluster_id}")

            profiles.append({
                "cluster_id": cluster_id,
                "cluster_name": name,
                "size_pct": round(size / total * 100, 1),
                "avg_age": round(avg_age, 1) if not np.isnan(avg_age) else None,
                "avg_spend": round(avg_spend, 0) if not np.isnan(avg_spend) else None,
                "avg_nights": round(avg_nights, 1) if not np.isnan(avg_nights) else None,
                "top_nationalities": top_nat,
                "top_accommodations": top_acc,
                "top_activities": top_activities,
                "top_motivations": top_motivations,
                "characteristics": characteristics,
            })

        # Re-order by avg_spend to match PLAN cluster definitions
        cluster_name_list = list(CLUSTER_NAMES.values())
        profiles.sort(key=lambda p: p["avg_spend"] or 0)
        for i, p in enumerate(profiles):
            old_id = p["cluster_id"]
            p["cluster_id"] = i
            if i < len(cluster_name_list):
                p["cluster_name"] = cluster_name_list[i]
            else:
                p["cluster_name"] = f"Cluster {i + 1}"

        return profiles
