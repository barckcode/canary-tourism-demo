"""Tests for K-Means tourist profiler."""

import json

from sqlalchemy import text

from app.models.profiler import CLUSTER_NAMES, TouristProfiler


def _load_raw_jsons(db):
    """Helper to load raw_json from microdata."""
    rows = db.execute(
        text("SELECT raw_json FROM microdata WHERE raw_json IS NOT NULL LIMIT 5000")
    ).fetchall()
    return [r[0] for r in rows]


def test_profiler_fit_produces_labels(db):
    """K-Means should produce cluster labels for all records."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    labels = profiler.fit(raw_jsons)
    assert len(labels) == len(raw_jsons)
    assert profiler.is_fitted


def test_profiler_produces_four_clusters(db):
    """Should produce exactly 4 clusters."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    labels = profiler.fit(raw_jsons)
    unique_labels = set(labels)
    assert len(unique_labels) == 4, f"Expected 4 clusters, got {unique_labels}"


def test_profiler_all_clusters_nonempty(db):
    """Every cluster should have at least some records."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    labels = profiler.fit(raw_jsons)
    for cluster_id in range(4):
        count = sum(1 for l in labels if l == cluster_id)
        assert count > 0, f"Cluster {cluster_id} is empty"


def test_profiler_get_profiles_structure(db):
    """Profile summaries should have all required fields."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    profiler.fit(raw_jsons)
    profiles = profiler.get_profiles()

    assert len(profiles) == 4

    required_fields = [
        "cluster_id", "cluster_name", "size_pct", "avg_age",
        "avg_spend", "avg_nights", "top_nationalities",
        "top_accommodations", "top_activities", "top_motivations",
        "characteristics",
    ]
    for p in profiles:
        for field in required_fields:
            assert field in p, f"Missing field '{field}' in profile {p['cluster_id']}"


def test_profiler_size_pct_sums_to_100(db):
    """Cluster size percentages should sum to approximately 100%."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    profiler.fit(raw_jsons)
    profiles = profiler.get_profiles()

    total_pct = sum(p["size_pct"] for p in profiles)
    assert abs(total_pct - 100.0) < 1.0, f"Size percentages sum to {total_pct}"


def test_profiler_avg_spend_positive(db):
    """Average spending should be positive for all clusters."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    profiler.fit(raw_jsons)
    profiles = profiler.get_profiles()

    for p in profiles:
        assert p["avg_spend"] is not None and p["avg_spend"] > 0, (
            f"Cluster {p['cluster_id']} has invalid avg_spend: {p['avg_spend']}"
        )


def test_profiler_nationalities_are_lists(db):
    """Top nationalities should be non-empty lists."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    profiler.fit(raw_jsons)
    profiles = profiler.get_profiles()

    for p in profiles:
        assert isinstance(p["top_nationalities"], list)
        assert len(p["top_nationalities"]) > 0, (
            f"Cluster {p['cluster_id']} has no nationalities"
        )


def test_profiler_cluster_names_fallback_with_extra_clusters(db):
    """When n_clusters exceeds CLUSTER_NAMES, extra clusters get fallback names."""
    raw_jsons = _load_raw_jsons(db)
    n = len(CLUSTER_NAMES) + 1  # one more than defined names
    profiler = TouristProfiler(n_clusters=n)
    profiler.fit(raw_jsons)
    profiles = profiler.get_profiles()

    assert len(profiles) == n
    names = [p["cluster_name"] for p in profiles]
    # First len(CLUSTER_NAMES) profiles should use the defined names
    defined_names = list(CLUSTER_NAMES.values())
    for name in defined_names:
        assert name in names, f"Expected defined name '{name}' in profiles"
    # The extra cluster should have a fallback name like "Cluster 5"
    fallback_names = [n for n in names if n not in defined_names]
    assert len(fallback_names) == 1
    assert fallback_names[0].startswith("Cluster ")


def test_profiler_cluster_names_no_index_error(db):
    """Cluster naming must not raise IndexError regardless of n_clusters."""
    raw_jsons = _load_raw_jsons(db)
    for n in (2, 3, 4, 5, 6):
        profiler = TouristProfiler(n_clusters=n)
        profiler.fit(raw_jsons)
        # This must not raise
        profiles = profiler.get_profiles()
        assert len(profiles) == n
        for p in profiles:
            assert isinstance(p["cluster_name"], str)
            assert len(p["cluster_name"]) > 0


def test_profiler_cluster_ids_match_kmeans_labels(db):
    """Profile cluster_ids must match original KMeans labels, not sorted index."""
    raw_jsons = _load_raw_jsons(db)
    profiler = TouristProfiler(n_clusters=4)
    labels = profiler.fit(raw_jsons)

    # The original KMeans cluster IDs
    original_ids = set(int(l) for l in labels)

    profiles = profiler.get_profiles()
    profile_ids = set(p["cluster_id"] for p in profiles)

    assert profile_ids == original_ids, (
        f"Profile cluster_ids {profile_ids} don't match KMeans labels {original_ids}"
    )

    # Verify each profile's cluster_id corresponds to actual records in that cluster
    for p in profiles:
        cid = p["cluster_id"]
        mask = labels == cid
        expected_size_pct = round(mask.sum() / len(labels) * 100, 1)
        assert p["size_pct"] == expected_size_pct, (
            f"Cluster {cid} size_pct {p['size_pct']} != expected {expected_size_pct}"
        )


def test_profiles_stored_in_db(db):
    """Profiles table should have been populated by trainer."""
    count = db.execute(text("SELECT COUNT(*) FROM profiles")).scalar()
    assert count == 4, f"Expected 4 profiles in DB, got {count}"


def test_profiles_db_has_valid_json(db):
    """Stored profiles should have valid JSON in text columns."""
    rows = db.execute(
        text("SELECT top_nationalities, top_accommodations FROM profiles")
    ).fetchall()
    for r in rows:
        nat = json.loads(r[0])
        assert isinstance(nat, list)
        acc = json.loads(r[1])
        assert isinstance(acc, list)
