"""Orquestador del pipeline Capa B — Geofísica Ambiental."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from layer_b.analytics.correlation import (
    compute_correlation,
    kolmogorov_smirnov_test,
    mann_whitney_test,
    permutation_test_mean_diff,
)
from layer_b.analytics.temporal import (
    cross_correlation,
    granger_causality_placeholder,
    rolling_correlation,
)
from layer_b.clustering.cluster_analysis import run_clustering
from layer_b.comparison.international import compare_regions
from layer_b.config import load_config
from layer_b.features.engineering import build_all_features, features_to_dict_map
from layer_b.formatting import parse_datetime_utc
from layer_b.ingestion.connectors import load_all_connectors
from layer_b.models import EnvironmentalObservation
from layer_b.normalization.timeseries_normalizer import normalize_observations
from layer_b.indices.environmental_indexes import compute_environmental_indexes
from layer_b.output.writers import (
    write_environmental_report,
    write_json_compact,
    write_parquet_records,
)
from layer_b.paths import ANALYTICS_DIR, FEATURES_DIR, NORMALIZED_DIR, REPORTS_DIR


def _daily_values(
    observations: list[EnvironmentalObservation],
    region_code: str,
    variable: str,
) -> list[float]:
    return [
        o.value
        for o in sorted(observations, key=lambda x: x.datetime_utc)
        if o.region_code == region_code and o.variable == variable
    ]


def run_pipeline(
    config_path: Path | None = None,
    use_synthetic: bool = True,
) -> dict[str, Any]:
    config = load_config(config_path)
    ref = parse_datetime_utc(config["project"]["reference_datetime_utc"])
    start = date.fromisoformat(config["project"]["start_date"])
    end = date.today()

    regions: list[str] = config["international_regions"]
    connector_names: list[str] = config["connectors"]
    primary = config["region"]["primary_region_code"]

    raw_rows = load_all_connectors(connector_names, regions, start, end)
    if not raw_rows and not use_synthetic:
        return {"layer": "B_geophysical", "status": "no_data"}

    observations = normalize_observations(raw_rows)
    normalized_records = [o.to_flat_dict() for o in observations]
    write_parquet_records(NORMALIZED_DIR / "environmental_normalized.parquet", normalized_records)

    all_features = []
    feature_maps: dict[str, dict[str, float]] = {}
    for region in regions:
        feats = build_all_features(observations, region, ref)
        all_features.extend(f.to_flat_dict() for f in feats)
        feature_maps[region] = features_to_dict_map(feats)

    write_parquet_records(FEATURES_DIR / "environmental_features.parquet", all_features)

    correlation_rows: list[dict[str, Any]] = []
    methods = config["statistics"]["correlation_methods"]
    for region in regions:
        sst_series = _daily_values(observations, region, "sst")
        rain_series = _daily_values(observations, region, "rainfall_mm")
        for method in methods:
            result = compute_correlation(
                region, "sst", sst_series, "rainfall_mm", rain_series, method
            )
            correlation_rows.append(result.model_dump())

    comparison_tests: list[dict[str, Any]] = []
    ref_rain = _daily_values(observations, primary, "rainfall_mm")
    for region in regions:
        if region == primary:
            continue
        other_rain = _daily_values(observations, region, "rainfall_mm")
        for test_fn in (mann_whitney_test, kolmogorov_smirnov_test, permutation_test_mean_diff):
            row = test_fn(ref_rain, other_rain)
            row["region_code"] = region
            row["reference_region"] = primary
            comparison_tests.append(row)

    temporal_rows: list[dict[str, Any]] = []
    sst_primary = _daily_values(observations, primary, "sst")
    rain_primary = _daily_values(observations, primary, "rainfall_mm")
    temporal_rows.append({**cross_correlation(sst_primary, rain_primary), "region_code": primary})
    temporal_rows.append({**rolling_correlation(sst_primary, rain_primary), "region_code": primary})
    temporal_rows.append({**granger_causality_placeholder(sst_primary, rain_primary), "region_code": primary})

    feature_names = sorted({
        f["feature_name"]
        for f in all_features
        if f.get("feature_value") is not None
    })
    matrix: list[list[float]] = []
    matrix_labels: list[str] = []
    for region in regions:
        row = [feature_maps[region].get(name, 0.0) for name in feature_names]
        if any(v != 0.0 for v in row):
            matrix.append(row)
            matrix_labels.append(region)

    cluster_rows = run_clustering(matrix, matrix_labels, config["clustering"]["methods"])

    primary_features = [
        f for f in all_features if f["region_code"] == primary
    ]
    # rebuild FeatureRecord list for indexes - simpler to recompute
    from layer_b.models import FeatureRecord
    feat_objs = [
        FeatureRecord(
            region_code=primary,
            reference_datetime_utc=ref,
            feature_name=f["feature_name"],
            feature_value=f.get("feature_value"),
            window_days=f.get("window_days"),
            evidence_level=f.get("evidence_level", "C"),
        )
        for f in primary_features
    ]
    indexes = compute_environmental_indexes(primary, ref, feat_objs)
    index_rows = [indexes.to_flat_dict()]

    key_features = [
        "sst_mean_7d", "rain_acc_7d", "soil_moisture_mean",
        "pressure_mean_7d", "earth_tide_mean",
    ]
    comparisons = compare_regions(primary, feature_maps, key_features)
    comparison_rows = [c.model_dump() for c in comparisons]

    write_parquet_records(ANALYTICS_DIR / "correlations.parquet", correlation_rows)
    write_parquet_records(ANALYTICS_DIR / "comparison_tests.parquet", comparison_tests)
    write_parquet_records(ANALYTICS_DIR / "temporal_analysis.parquet", temporal_rows)
    write_parquet_records(ANALYTICS_DIR / "clustering.parquet", cluster_rows)
    write_parquet_records(ANALYTICS_DIR / "environmental_indexes.parquet", index_rows)
    write_parquet_records(ANALYTICS_DIR / "international_comparison.parquet", comparison_rows)

    report_path = REPORTS_DIR / f"reporte_ambiental_{primary}.md"
    write_environmental_report(
        report_path,
        primary,
        ref,
        indexes,
        comparison_rows,
        correlation_rows,
    )

    summary = {
        "layer": "B_geophysical",
        "primary_region": primary,
        "reference_datetime_utc": config["project"]["reference_datetime_utc"],
        "observations_normalized": len(normalized_records),
        "features_computed": len(all_features),
        "correlations": len(correlation_rows),
        "international_comparisons": len(comparison_rows),
        "cluster_assignments": len(cluster_rows),
        "environmental_anomaly_index": indexes.environmental_anomaly_index,
        "outputs": {
            "normalized": str(NORMALIZED_DIR / "environmental_normalized.parquet"),
            "features": str(FEATURES_DIR / "environmental_features.parquet"),
            "indexes": str(ANALYTICS_DIR / "environmental_indexes.parquet"),
            "international_comparison": str(ANALYTICS_DIR / "international_comparison.parquet"),
            "report": str(report_path),
        },
    }
    write_json_compact(ANALYTICS_DIR / "pipeline_summary.json", summary)
    return summary
