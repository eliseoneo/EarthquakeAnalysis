"""Orquestador del pipeline Capa A."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from layer_a.config import load_config
from layer_a.formatting import parse_datetime_utc
from layer_a.geospatial.spatial_join import associate_faults_and_plates
from layer_a.ingestion.catalog_loader import load_raw_or_fixture
from layer_a.ingestion.funvisis_client import download_and_save_funvisis
from layer_a.ingestion.ingv_client import download_and_save_ingv
from layer_a.ingestion.sgc_client import download_and_save_sgc
from layer_a.ingestion.usgs_client import download_and_save_usgs
from layer_a.models import SeismicEvent
from layer_a.normalization.event_normalizer import normalize_catalog
from layer_a.output.writers import (
    write_geojson_events,
    write_json_compact,
    write_mainshock_report,
    write_parquet_records,
)
from layer_a.persistence import persist_run
from layer_a.paths import FIXTURES_DIR, PROCESSED_DIR, RAW_DIR, REPORTS_DIR
from layer_a.quality.deduplication import deduplicate_events
from layer_a.tectonic.aftershocks import apply_aftershock_metrics, detect_aftershocks
from layer_a.tectonic.doublets import detect_doublets
from layer_a.tectonic.indexes import compute_tectonic_indexes
from layer_a.tectonic.omori import fit_omori_utsu
from layer_a.tectonic.windows import build_temporal_windows


def _find_target_mainshock(
    catalog: list[SeismicEvent],
    target: dict[str, Any],
) -> SeismicEvent | None:
    target_dt = parse_datetime_utc(str(target["datetime_utc"]))

    for event in catalog:
        if event.event_id == target.get("event_id"):
            return event.model_copy(update={"is_mainshock": True, "confidence_level": "A"})

    closest = None
    best_delta = float("inf")
    for event in catalog:
        if event.magnitude < target.get("magnitude", 6.0) - 0.5:
            continue
        delta = abs((event.datetime_utc - target_dt).total_seconds())
        dist = abs(event.latitude - target["latitude"]) + abs(event.longitude - target["longitude"])
        score = delta + dist * 3600
        if score < best_delta:
            best_delta = score
            closest = event

    if closest:
        return closest.model_copy(update={"is_mainshock": True, "confidence_level": "A"})
    return None


def run_pipeline(
    config_path: Path | None = None,
    output_dir: Path | None = None,
    use_fixtures: bool = True,
    download_usgs: bool = False,
    download_ingv: bool = False,
    download_sgc: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    out = output_dir or PROCESSED_DIR
    out.mkdir(parents=True, exist_ok=True)

    usgs_download_status = "skipped"
    funvisis_download_status = "skipped"
    ingv_download_status = "skipped"
    sgc_download_status = "skipped"
    if download_usgs:
        try:
            _, usgs_download_status = download_and_save_usgs(config)
        except Exception as exc:
            usgs_download_status = f"failed ({type(exc).__name__}: {exc})"

    if download_ingv:
        try:
            _, ingv_download_status = download_and_save_ingv(config)
        except Exception as exc:
            ingv_download_status = f"failed ({type(exc).__name__}: {exc})"

    if download_sgc:
        try:
            _, sgc_download_status = download_and_save_sgc(config)
        except Exception as exc:
            sgc_download_status = f"failed ({type(exc).__name__}: {exc})"

    funvisis_raw_path = RAW_DIR / "catalog_funvisis.json"
    if funvisis_raw_path.exists():
        funvisis_download_status = "existing_raw"
    elif "funvisis" in config["catalog"]["sources"]:
        try:
            _, funvisis_download_status = download_and_save_funvisis(config)
        except Exception as exc:
            funvisis_download_status = f"failed ({type(exc).__name__}: {exc})"

    raw_by_source: dict[str, list[dict[str, Any]]] = {}
    for source in config["catalog"]["sources"]:
        raw_by_source[source] = load_raw_or_fixture(source, use_fixtures=use_fixtures)

    funvisis_source_mode = "missing"
    if raw_by_source.get("funvisis"):
        if str(funvisis_download_status).startswith("ok (endpoint"):
            funvisis_source_mode = "endpoint_official"
        elif funvisis_raw_path.exists():
            funvisis_source_mode = "raw_local"
        else:
            funvisis_source_mode = "fixture_only"
    elif use_fixtures:
        funvisis_source_mode = "fixture_only"

    normalized: list[SeismicEvent] = []
    for source, rows in raw_by_source.items():
        normalized.extend(normalize_catalog(rows, source))

    write_parquet_records(
        out / "catalog_normalized.parquet",
        [e.to_flat_dict() for e in normalized],
    )

    deduped = deduplicate_events(
        normalized,
        config["deduplication"],
        config["catalog"]["source_priority"],
    )
    write_parquet_records(
        out / "catalog_deduplicated.parquet",
        [e.to_flat_dict() for e in deduped],
    )

    faults_path = FIXTURES_DIR / "faults_sample.geojson"
    plates_path = FIXTURES_DIR / "plates_sample.geojson"
    with_faults = associate_faults_and_plates(deduped, faults_path, plates_path)
    write_parquet_records(
        out / "catalog_with_faults.parquet",
        [e.to_flat_dict() for e in with_faults],
    )
    write_geojson_events(out / "catalog_with_faults.geojson", with_faults)

    mainshock = _find_target_mainshock(with_faults, config["target_mainshock"])
    aftershock_sequences = []
    doublet_candidates = detect_doublets(with_faults, config["doublets"])
    window_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    report_path = REPORTS_DIR / "reporte_evento_venezuela_2026_06_24.md"

    if mainshock:
        tagged_aftershocks, sequence = detect_aftershocks(
            mainshock,
            with_faults,
            time_window_days=config["aftershocks"]["max_days"],
            radius_km=config["aftershocks"]["radius_km"],
            extended_radius_km=config["aftershocks"]["extended_radius_km"],
        )
        aftershock_sequences.append(sequence.model_dump())
        mainshock = apply_aftershock_metrics(mainshock, sequence)

        window_rows = build_temporal_windows(
            mainshock,
            with_faults,
            config["temporal_windows_days"],
        )

        omori = fit_omori_utsu(mainshock.datetime_utc, tagged_aftershocks)
        recent = [
            e for e in with_faults
            if mainshock.datetime_utc - timedelta(days=90) <= e.datetime_utc < mainshock.datetime_utc
        ]
        indexes = compute_tectonic_indexes(mainshock, recent, omori.observed_vs_expected_rate)
        index_rows.append(indexes.model_dump())

        related_doublets = [
            d for d in doublet_candidates
            if d.event_id_1 == mainshock.event_id or d.event_id_2 == mainshock.event_id
        ]
        write_mainshock_report(
            report_path,
            mainshock,
            sequence,
            related_doublets,
            indexes,
            source_status={
                "usgs_download_status": usgs_download_status,
                "funvisis_download_status": funvisis_download_status,
                "funvisis_source_mode": funvisis_source_mode,
            },
        )

    write_parquet_records(out / "mainshock_windows.parquet", window_rows)
    write_parquet_records(out / "aftershock_sequences.parquet", aftershock_sequences)
    write_parquet_records(
        out / "doublet_candidates.parquet",
        [d.model_dump() for d in doublet_candidates],
    )
    write_parquet_records(out / "tectonic_indexes.parquet", index_rows)

    summary = {
        "layer": "A_tectonic",
        "usgs_download_status": usgs_download_status,
        "funvisis_download_status": funvisis_download_status,
        "funvisis_source_mode": funvisis_source_mode,
        "ingv_download_status": ingv_download_status,
        "sgc_download_status": sgc_download_status,
        "events_normalized": len(normalized),
        "events_deduplicated": len(deduped),
        "events_with_faults": len(with_faults),
        "aftershock_sequences": len(aftershock_sequences),
        "doublet_candidates": len(doublet_candidates),
        "mainshock_id": mainshock.event_id if mainshock else None,
        "outputs": {
            "catalog_deduplicated": str(out / "catalog_deduplicated.parquet"),
            "catalog_with_faults": str(out / "catalog_with_faults.parquet"),
            "aftershock_sequences": str(out / "aftershock_sequences.parquet"),
            "doublet_candidates": str(out / "doublet_candidates.parquet"),
            "tectonic_indexes": str(out / "tectonic_indexes.parquet"),
            "report": str(report_path),
        },
    }
    summary_path = out / "pipeline_summary.json"
    write_json_compact(summary_path, summary)

    artifacts = {
        "summary": summary_path,
        "catalog_deduplicated": out / "catalog_deduplicated.parquet",
        "catalog_with_faults": out / "catalog_with_faults.parquet",
        "catalog_with_faults_geojson": out / "catalog_with_faults.geojson",
        "aftershock_sequences": out / "aftershock_sequences.parquet",
        "doublet_candidates": out / "doublet_candidates.parquet",
        "tectonic_indexes": out / "tectonic_indexes.parquet",
        "report": report_path,
    }
    summary["persistence"] = persist_run(summary, artifacts)
    write_json_compact(summary_path, summary)
    return summary
