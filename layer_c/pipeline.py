"""Pipeline de estructuracion H04 para analisis del evento Venezuela 2026."""

from __future__ import annotations

import csv
import json
import hashlib
from pathlib import Path
from typing import Any
import urllib.request
from datetime import datetime, timezone

import yaml

from layer_c.config import load_config
from layer_c.paths import PROCESSED_DIR, RAW_DIR, NORMALIZED_DIR, REFERENCE_DOC, REPORTS_DIR, REPO_ROOT
from layer_c.persistence import persist_run


LAYER_A_ROOT = REPO_ROOT / "layer_a_tectonic"
LAYER_A_RAW_DIR = LAYER_A_ROOT / "data" / "raw"
LAYER_A_FIXTURES_DIR = LAYER_A_ROOT / "data" / "fixtures" / "synthetic"
LAYER_A_PROCESSED_DIR = LAYER_A_ROOT / "data" / "processed"
LAYER_A_SUMMARY_PATH = LAYER_A_PROCESSED_DIR / "pipeline_summary.json"
EVENT_CASE_PATH = REPO_ROOT / "event_cases" / "venezuela_2026_june" / "event.yaml"

CATALOG_SOURCES = {
    "usgs": {
        "source_name": "USGS",
        "raw_path": LAYER_A_RAW_DIR / "catalog_usgs.json",
        "fixture_path": LAYER_A_FIXTURES_DIR / "catalog_usgs_sample.json",
    },
    "funvisis": {
        "source_name": "FUNVISIS",
        "raw_path": LAYER_A_RAW_DIR / "catalog_funvisis.json",
        "fixture_path": LAYER_A_FIXTURES_DIR / "catalog_funvisis_sample.json",
    },
}

ACCELEROGRAPHY_RAW_PATH = RAW_DIR / "accelerography" / "accelerography_station_estimates.json"
ACCELEROGRAPHY_NORMALIZED_PATH = NORMALIZED_DIR / "accelerography_station_records.json"
GEOTECHNICAL_NORMALIZED_PATH = NORMALIZED_DIR / "geotechnical_site_records.json"
FUNVISIS_OFFICIAL_DUMP_PATH = RAW_DIR / "funvisis" / "catalog_funvisis_official.json"


def _ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        payload = yaml.safe_load(fh)
    return payload if isinstance(payload, dict) else {}


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.exists() and path.suffix == ".parquet":
        try:
            import pandas as pd
            rows = pd.read_parquet(path).to_dict(orient="records")
            return [
                {str(key): value for key, value in row.items()}
                for row in rows
            ]
        except ImportError:
            fallback = path.with_suffix(".json")
            if fallback.exists():
                payload = _read_json(fallback)
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict):
                    return payload.get("events", payload.get("records", []))
            return []
    if path.exists():
        payload = _read_json(path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("events", payload.get("records", []))
    return []


def _read_event_count(path: Path) -> int:
    if not path.exists():
        return 0
    payload = _read_json(path)
    if isinstance(payload, dict):
        if isinstance(payload.get("event_count"), int):
            return payload["event_count"]
        events = payload.get("events", [])
        if isinstance(events, list):
            return len(events)
    if isinstance(payload, list):
        return len(payload)
    return 0


def _availability_status(raw_path: Path, fixture_path: Path) -> tuple[str, str]:
    if raw_path.exists():
        return "available_raw", "layer_a_raw_and_processed"
    if fixture_path.exists():
        return "fixture_only", "layer_a_fixture_and_processed"
    return "missing", "not_collected"


def _load_layer_a_summary() -> dict[str, Any] | None:
    if not LAYER_A_SUMMARY_PATH.exists():
        return None
    payload = _read_json(LAYER_A_SUMMARY_PATH)
    return payload if isinstance(payload, dict) else None


def _load_event_case() -> dict[str, Any] | None:
    if not EVENT_CASE_PATH.exists():
        return None
    payload = _read_yaml(EVENT_CASE_PATH)
    return payload if isinstance(payload, dict) else None


def _resolve_repo_path(path_str: str | None, fallback: Path) -> Path:
    if not path_str:
        return fallback
    candidate = REPO_ROOT / path_str
    return candidate


def _data_sources_config(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("data_sources", {}) if isinstance(config, dict) else {}


def _external_source_registry_config(config: dict[str, Any]) -> dict[str, Any]:
    data_sources = _data_sources_config(config)
    registry = data_sources.get("external_source_registry", {}) if isinstance(data_sources, dict) else {}
    return registry if isinstance(registry, dict) else {}


def _event_case_seismic(event_case: dict[str, Any] | None) -> dict[str, Any]:
    return ((event_case or {}).get("advanced_features") or {}).get("seismic") or {}


def _event_case_geotech(event_case: dict[str, Any] | None) -> dict[str, Any]:
    return ((event_case or {}).get("advanced_features") or {}).get("geological_geotechnical") or {}


def _read_accelerography_json_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = _read_json(path)
    if isinstance(payload, dict):
        records = payload.get("records", payload.get("events", []))
        return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    return []


def _read_accelerography_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _coerce_real_accelerography_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
    return {
        "record_id": str(record.get("record_id", f"acc_real_{index:03d}")),
        "event_id": str(record.get("event_id", "venezuela_2026_06_24_h04")),
        "station_id": str(record.get("station_id", f"station_{index:03d}")),
        "station_name": str(record.get("station_name", record.get("location_name", f"station_{index:03d}"))),
        "network_code": str(record.get("network_code", "unknown")),
        "source": str(record.get("source", "unknown")),
        "measurement_mode": str(record.get("measurement_mode", "instrumented_strong_motion")),
        "datetime_utc": str(record.get("datetime_utc", "2026-06-24 22:05:11")),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "elevation_m": record.get("elevation_m"),
        "component": str(record.get("component", "H")),
        "sampling_hz": record.get("sampling_hz"),
        "instrument_type": str(record.get("instrument_type", "accelerograph")),
        "pga_g": record.get("pga_g"),
        "pgv_cm_per_s": record.get("pgv_cm_per_s"),
        "pgd_cm": record.get("pgd_cm"),
        "sa_0_3s_g": record.get("sa_0_3s_g"),
        "sa_1_0s_g": record.get("sa_1_0s_g"),
        "sa_3_0s_g": record.get("sa_3_0s_g"),
        "mmi_equivalent": record.get("mmi_equivalent"),
        "site_class": str(record.get("site_class", "unknown")),
        "vs30_m_per_s": record.get("vs30_m_per_s"),
        "soil_type": str(record.get("soil_type", "unknown")),
        "basin_context": str(record.get("basin_context", "")),
        "distance_to_epicenter_km": record.get("distance_to_epicenter_km"),
        "distance_to_fault_km": record.get("distance_to_fault_km"),
        "processing_level": str(record.get("processing_level", "raw")),
        "quality_flag": str(record.get("quality_flag", "B")),
        "uncertainty_notes": str(record.get("uncertainty_notes", "")),
        "provenance": {
            "artifact_type": str(provenance.get("artifact_type", "station_record")),
            "source_reference": str(provenance.get("source_reference", record.get("source", "unknown"))),
            "downloaded_at_utc": str(provenance.get("downloaded_at_utc", "")),
            "license": str(provenance.get("license", "unknown")),
            "notes": str(provenance.get("notes", "")),
        },
    }


def _load_real_accelerography_raw_payload(config: dict[str, Any]) -> dict[str, Any] | None:
    data_sources = _data_sources_config(config)
    accelerography_cfg = data_sources.get("accelerography", {}) if isinstance(data_sources, dict) else {}
    json_path = _resolve_repo_path(accelerography_cfg.get("raw_station_path"), RAW_DIR / "accelerography" / "accelerography_station_records.json")
    csv_path = _resolve_repo_path(accelerography_cfg.get("raw_station_csv_path"), RAW_DIR / "accelerography" / "accelerography_station_records.csv")

    records = _read_accelerography_json_records(json_path)
    source_label = "accelerography_station_records.json"
    if not records:
        records = _read_accelerography_csv_records(csv_path)
        source_label = "accelerography_station_records.csv"
    if not records:
        return None

    coerced = [_coerce_real_accelerography_record(record, index) for index, record in enumerate(records, start=1)]
    return {
        "source": source_label,
        "event_id": "venezuela_2026_06_24_h04",
        "record_count": len(coerced),
        "records": coerced,
    }


def _build_accelerography_raw_payload(event_case: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]:
    real_payload = _load_real_accelerography_raw_payload(config)
    if real_payload is not None:
        return real_payload

    seismic = _event_case_seismic(event_case)
    estimates = seismic.get("pga_station_estimates", [])
    records: list[dict[str, Any]] = []
    for index, estimate in enumerate(estimates, start=1):
        if not isinstance(estimate, dict):
            continue
        records.append({
            "record_id": f"acc_h04_{index:03d}",
            "event_id": "venezuela_2026_06_24_h04",
            "station_id": f"h04_station_{index:03d}",
            "station_name": str(estimate.get("location", f"station_{index:03d}")),
            "network_code": "DYFI",
            "source": str(estimate.get("source", "USGS ShakeMap")),
            "measurement_mode": str(seismic.get("pga_measurement_quality", "estimated_shakemap")),
            "datetime_utc": "2026-06-24 22:05:11",
            "latitude": None,
            "longitude": None,
            "component": "H",
            "sampling_hz": None,
            "instrument_type": "shakemap_cell",
            "pga_g": estimate.get("pga_g", seismic.get("pga_g")),
            "pgv_cm_per_s": seismic.get("pgv_cm_per_s"),
            "pgd_cm": None,
            "sa_0_3s_g": None,
            "sa_1_0s_g": None,
            "sa_3_0s_g": None,
            "mmi_equivalent": seismic.get("mmi_intensity"),
            "site_class": str(estimate.get("site_class", "unknown")),
            "vs30_m_per_s": None,
            "soil_type": "unknown",
            "basin_context": str(estimate.get("site_class", "")),
            "distance_to_epicenter_km": None,
            "distance_to_fault_km": None,
            "processing_level": "aggregated",
            "quality_flag": "B",
            "uncertainty_notes": str(estimate.get("notes", "")),
            "provenance": {
                "artifact_type": "shakemap_cell",
                "source_reference": str(estimate.get("source", "USGS ShakeMap")),
                "downloaded_at_utc": "",
                "license": "unknown",
                "notes": str(estimate.get("estimate_method", "")),
            },
        })

    if not records and seismic.get("pga_g") is not None:
        records.append({
            "record_id": "acc_h04_aggregate_001",
            "event_id": "venezuela_2026_06_24_h04",
            "station_id": "aggregate_case_level",
            "station_name": "Estimacion agregada caso Venezuela 2026",
            "network_code": "CASE",
            "source": "event_cases/venezuela_2026_june/event.yaml",
            "measurement_mode": str(seismic.get("pga_measurement_quality", "estimated_shakemap")),
            "datetime_utc": "2026-06-24 22:05:11",
            "latitude": None,
            "longitude": None,
            "component": "H",
            "sampling_hz": None,
            "instrument_type": "aggregated_case_level",
            "pga_g": seismic.get("pga_g"),
            "pgv_cm_per_s": seismic.get("pgv_cm_per_s"),
            "pgd_cm": None,
            "sa_0_3s_g": None,
            "sa_1_0s_g": None,
            "sa_3_0s_g": None,
            "mmi_equivalent": seismic.get("mmi_intensity"),
            "site_class": "unknown",
            "vs30_m_per_s": None,
            "soil_type": "unknown",
            "basin_context": "",
            "distance_to_epicenter_km": None,
            "distance_to_fault_km": None,
            "processing_level": "aggregated",
            "quality_flag": "C",
            "uncertainty_notes": "Estimacion agregada sin registros instrumentales por estacion en el repo.",
            "provenance": {
                "artifact_type": "historical_estimate",
                "source_reference": "event_cases/venezuela_2026_june/event.yaml",
                "downloaded_at_utc": "",
                "license": "repo_internal",
                "notes": "Bootstrap de Capa C desde advanced_features.seismic.",
            },
        })

    return {
        "source": "layer_c_accelerography_bootstrap",
        "event_id": "venezuela_2026_06_24_h04",
        "record_count": len(records),
        "records": records,
    }


def _normalize_accelerography_records(raw_payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for record in raw_payload.get("records", []):
        if not isinstance(record, dict):
            continue
        normalized.append({
            "record_id": str(record.get("record_id", "")),
            "event_id": str(record.get("event_id", "")),
            "station_id": str(record.get("station_id", "")),
            "station_name": str(record.get("station_name", "")),
            "source": str(record.get("source", "")),
            "measurement_mode": str(record.get("measurement_mode", "unknown")),
            "component": str(record.get("component", "unknown")),
            "pga_g": record.get("pga_g"),
            "pgv_cm_per_s": record.get("pgv_cm_per_s"),
            "site_class": str(record.get("site_class", "unknown")),
            "processing_level": str(record.get("processing_level", "aggregated")),
            "quality_flag": str(record.get("quality_flag", "unknown")),
            "provenance_reference": str((record.get("provenance") or {}).get("source_reference", "")),
        })
    return normalized


def _build_geotechnical_site_records(event_case: dict[str, Any] | None) -> list[dict[str, Any]]:
    geotech = _event_case_geotech(event_case)
    if not geotech:
        return []
    return [{
        "site_id": "geo_h04_001",
        "event_id": "venezuela_2026_06_24_h04",
        "location_name": "Corredor urbano Venezuela 2026",
        "latitude": 10.48,
        "longitude": -66.90,
        "administrative_area": "Caracas-La Guaira-Valencia",
        "soil_type": str(geotech.get("soil_type", "unknown")),
        "lithology": str(geotech.get("lithology", "unknown")),
        "vs30_m_per_s": geotech.get("vs30_m_per_s"),
        "site_class_nehrp": "D" if float(geotech.get("vs30_m_per_s", 0) or 0) < 360 else "C",
        "sedimentary_basin": str(geotech.get("sedimentary_basin", "")),
        "microzonification_unit": "pendiente",
        "water_table_depth_m": None,
        "slope_degrees": geotech.get("slope_degrees"),
        "topographic_amplification_index": None,
        "liquefaction_likelihood": "moderate",
        "landslide_susceptibility": "high",
        "surface_geology_context": str(geotech.get("location_geology_context", "")),
        "distance_to_fault_km": None,
        "distance_to_coast_or_river_km": geotech.get("distance_to_coast_or_rivers_km"),
        "observed_damage_pattern": "variacion espacial esperada por tipo de suelo y ladera",
        "site_response_notes": "Registro derivado del caso H04; pendiente de microzonificacion formal.",
        "quality_flag": "C",
        "provenance": {
            "source_reference": "event_cases/venezuela_2026_june/event.yaml",
            "artifact_type": "inferred_case_level",
            "downloaded_at_utc": "",
            "notes": "Bootstrap geotecnico desde advanced_features.geological_geotechnical.",
        },
    }]


def _fetch_funvisis_endpoint(endpoint: str, timeout_seconds: int) -> Any:
    with urllib.request.urlopen(endpoint, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_funvisis_depth_km(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("km", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_funvisis_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _parse_funvisis_datetime(date_str: Any, time_str: Any) -> str:
    date_text = str(date_str or "").strip()
    time_text = str(time_str or "00:00").strip()
    try:
        dt = datetime.strptime(f"{date_text} {time_text}", "%d-%m-%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return f"{date_text} {time_text}".strip()


def _build_funvisis_event_id(dt_text: str, lat: float | None, lon: float | None, mag: float | None) -> str:
    seed = f"{dt_text}|{lat}|{lon}|{mag}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()[:16]
    return f"funvisis_{digest}"


def _normalize_funvisis_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None

    coordinates = geometry.get("coordinates", [])
    lon = None
    lat = None
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        lon = _parse_funvisis_float(coordinates[0])
        lat = _parse_funvisis_float(coordinates[1])
    if lat is None:
        lat = _parse_funvisis_float(properties.get("lat"))
    if lon is None:
        lon = _parse_funvisis_float(properties.get("long"))

    mag = _parse_funvisis_float(properties.get("value"))
    depth_km = _parse_funvisis_depth_km(properties.get("depth"))
    event_time_utc = _parse_funvisis_datetime(properties.get("date"), properties.get("time"))
    event_id = _build_funvisis_event_id(event_time_utc, lat, lon, mag)

    return {
        "event_id": event_id,
        "source": "funvisis",
        "source_event_id": event_id,
        "datetime_utc": event_time_utc,
        "latitude": lat,
        "longitude": lon,
        "depth_km": depth_km,
        "magnitude": mag,
        "magnitude_type": "Mw",
        "place": str(properties.get("addressFormatted", "")),
        "status": "reviewed",
        "country": str(properties.get("country", "Venezuela")),
        "raw_properties": properties,
    }


def _normalize_funvisis_dump(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features", [])
        normalized_events = []
        if isinstance(features, list):
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                normalized = _normalize_funvisis_feature(feature)
                if normalized is not None:
                    normalized_events.append(normalized)
        return {
            "source": "funvisis",
            "event_count": len(normalized_events),
            "events": normalized_events,
            "source_format": "feature_collection_recent_events",
            "historical_scope": "recent_events_only",
            "documented_filters": False,
        }
    if isinstance(payload, dict):
        events = payload.get("events", payload.get("records", []))
        if isinstance(events, list):
            return {
                "source": str(payload.get("source", "funvisis")),
                "event_count": len(events),
                "events": events,
            }
    if isinstance(payload, list):
        return {
            "source": "funvisis",
            "event_count": len(payload),
            "events": payload,
        }
    return {
        "source": "funvisis",
        "event_count": 0,
        "events": [],
    }


def _resolve_funvisis_connector(
    config: dict[str, Any],
    catalog_event_candidates: list[dict[str, Any]],
    layer_a_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    data_sources = _data_sources_config(config)
    funvisis_cfg = data_sources.get("funvisis", {}) if isinstance(data_sources, dict) else {}
    official_dump_path = _resolve_repo_path(funvisis_cfg.get("official_dump_path"), FUNVISIS_OFFICIAL_DUMP_PATH)
    endpoint = funvisis_cfg.get("endpoint")
    timeout_seconds = int(funvisis_cfg.get("timeout_seconds", 20))
    fallback_provider = str(funvisis_cfg.get("fallback_provider", "USGS"))

    if isinstance(endpoint, str) and endpoint.strip():
        try:
            payload = _fetch_funvisis_endpoint(endpoint.strip(), timeout_seconds)
            normalized = _normalize_funvisis_dump(payload)
            _write_json(official_dump_path, normalized)
            return {
                "status": "available_endpoint",
                "data_mode": "funvisis_official_endpoint",
                "artifact_path": str(official_dump_path),
                "record_count": int(normalized.get("event_count", 0)),
                "source_reference": endpoint.strip(),
                "notes": (
                    "Catalogo oficial obtenido desde endpoint configurado. "
                    "La fuente observada parece orientada a eventos recientes y sin filtros documentados."
                ),
            }
        except Exception as exc:
            endpoint_error = f"{type(exc).__name__}: {exc}"
        else:
            endpoint_error = ""
    else:
        endpoint_error = ""

    if official_dump_path.exists():
        normalized = _normalize_funvisis_dump(_read_json(official_dump_path))
        _write_json(official_dump_path, normalized)
        return {
            "status": "available_dump",
            "data_mode": "funvisis_official_dump",
            "artifact_path": str(official_dump_path),
            "record_count": int(normalized.get("event_count", 0)),
            "source_reference": str(official_dump_path),
            "notes": (
                "Catalogo oficial cargado desde dump estable en Capa C. "
                "La fuente observada parece orientada a eventos recientes y sin filtros documentados."
            ),
        }

    meta = CATALOG_SOURCES["funvisis"]
    if meta["raw_path"].exists():
        layer_a_mode = str((layer_a_summary or {}).get("funvisis_source_mode", "raw_local"))
        return {
            "status": "available_endpoint" if layer_a_mode == "endpoint_official" else "available_raw",
            "data_mode": "funvisis_official_endpoint" if layer_a_mode == "endpoint_official" else "layer_a_raw_and_processed",
            "artifact_path": str(meta["raw_path"]),
            "record_count": _read_event_count(meta["raw_path"]),
            "source_reference": "FUNVISIS raw catalog",
            "notes": "Catalogo oficial disponible en Capa A desde endpoint observado." if layer_a_mode == "endpoint_official" else "Catalogo oficial disponible en Capa A.",
        }

    usgs_proxy_rows = [row for row in catalog_event_candidates if row.get("source") == "usgs"]
    proxy_payload = {
        "source": "funvisis_fallback_proxy",
        "fallback_provider": fallback_provider,
        "official_funvisis_endpoint_available": False,
        "fallback_reason": "No existe endpoint o formato oficial FUNVISIS en el repo actual.",
        "endpoint_error": endpoint_error,
        "record_count": len(usgs_proxy_rows),
        "events": usgs_proxy_rows,
    }
    proxy_path = RAW_DIR / "catalog_funvisis_fallback_proxy.json"
    _write_json(proxy_path, proxy_payload)

    return {
        "status": "fallback_proxy",
        "data_mode": "usgs_proxy_for_funvisis",
        "artifact_path": str(proxy_path),
        "record_count": len(usgs_proxy_rows),
        "source_reference": f"{fallback_provider} proxy for FUNVISIS",
        "notes": "Fallback temporal mientras no exista conector oficial FUNVISIS.",
    }


def _build_catalog_source_coverage(layer_a_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    processed_catalog_path = LAYER_A_PROCESSED_DIR / "catalog_with_faults.parquet"
    processed_records = _read_records(processed_catalog_path)

    for source_key, meta in CATALOG_SOURCES.items():
        status, data_mode = _availability_status(meta["raw_path"], meta["fixture_path"])
        connector_status = "unknown"
        matching_processed = [
            row for row in processed_records
            if str(row.get("source", "")).lower() == source_key
        ]
        if source_key == "funvisis" and isinstance(layer_a_summary, dict):
            connector_status = str(
                layer_a_summary.get("funvisis_source_mode")
                or layer_a_summary.get("funvisis_download_status")
                or "unknown"
            )
        elif source_key == "usgs":
            connector_status = "raw_local" if meta["raw_path"].exists() else "unknown"
        rows.append({
            "source_key": source_key,
            "source_name": meta["source_name"],
            "availability_status": status,
            "data_mode": data_mode,
            "connector_status": connector_status,
            "raw_path": str(meta["raw_path"]) if meta["raw_path"].exists() else "",
            "fixture_path": str(meta["fixture_path"]) if meta["fixture_path"].exists() else "",
            "processed_catalog_path": str(processed_catalog_path) if processed_catalog_path.exists() else "",
            "raw_record_count": _read_event_count(meta["raw_path"]),
            "fixture_record_count": _read_event_count(meta["fixture_path"]),
            "processed_record_count": len(matching_processed),
            "layer_a_run_available": layer_a_summary is not None,
            "layer_a_mainshock_id": (
                layer_a_summary.get("mainshock_id")
                if isinstance(layer_a_summary, dict)
                else None
            ),
        })
    return rows


def _build_catalog_event_candidates(
    config: dict[str, Any],
    layer_a_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    catalog_path = LAYER_A_PROCESSED_DIR / "catalog_with_faults.parquet"
    rows = _read_records(catalog_path)
    event_date = str(config["event"]["date_utc"])
    target_sources = set(CATALOG_SOURCES.keys())
    target_mainshock_id = (
        str(layer_a_summary.get("mainshock_id"))
        if isinstance(layer_a_summary, dict) and layer_a_summary.get("mainshock_id")
        else ""
    )

    selected: list[dict[str, Any]] = []
    for row in rows:
        source = str(row.get("source", "")).lower()
        dt = str(row.get("datetime_utc", ""))
        if source not in target_sources:
            continue
        if not dt.startswith(event_date):
            continue
        selected.append({
            "event_id": row.get("event_id", ""),
            "source": source,
            "datetime_utc": dt,
            "magnitude": row.get("magnitude"),
            "magnitude_type": row.get("magnitude_type"),
            "depth_km": row.get("depth_km"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
            "place": row.get("place", ""),
            "is_mainshock": str(row.get("event_id", "")) == target_mainshock_id,
            "nearest_fault_name": row.get("nearest_fault_name"),
            "distance_to_nearest_fault_km": row.get("distance_to_nearest_fault_km"),
            "nearest_plate_boundary": row.get("nearest_plate_boundary"),
            "plate_context": row.get("plate_context"),
            "moment_tensor_available": bool(row.get("moment_tensor_available", False)),
            "rake": row.get("rake"),
            "focal_mechanism_type": row.get("focal_mechanism_type"),
        })

    selected.sort(key=lambda item: (item["datetime_utc"], -(item["magnitude"] or 0)))
    return selected


def _build_source_coverage_matrix(
    config: dict[str, Any],
    source_coverage: list[dict[str, Any]],
    event_case: dict[str, Any] | None,
    accelerography_payload: dict[str, Any],
    accelerography_records: list[dict[str, Any]],
    funvisis_connector: dict[str, Any],
) -> list[dict[str, Any]]:
    source_lookup = {row["source_name"]: row for row in source_coverage}
    matrix: list[dict[str, Any]] = []
    event_case_path = str(EVENT_CASE_PATH) if EVENT_CASE_PATH.exists() else ""
    seismic = _event_case_seismic(event_case)
    geotech = _event_case_geotech(event_case)

    for evidence in config["evidence_lines"]:
        evidence_id = evidence["evidence_id"]
        evidence_type = evidence["evidence_type"]
        for source_name in evidence.get("source_candidates", []):
            availability_status = "missing"
            data_mode = "not_collected"
            record_count = 0
            artifact_path = ""
            supports_h04 = False
            gaps: list[str] = []
            next_action = "recolectar evidencia"

            source_row = source_lookup.get(source_name)
            if source_row:
                availability_status = source_row["availability_status"]
                data_mode = source_row["data_mode"]
                record_count = int(source_row.get("processed_record_count", 0))
                artifact_path = source_row.get("processed_catalog_path", "")
                supports_h04 = availability_status != "missing"
                if source_name == "FUNVISIS" and funvisis_connector["status"] == "fallback_proxy":
                    availability_status = "fallback_proxy"
                    data_mode = funvisis_connector["data_mode"]
                    record_count = int(funvisis_connector.get("record_count", 0))
                    artifact_path = funvisis_connector.get("artifact_path", "")
                    supports_h04 = record_count > 0
                    gaps.append("sin endpoint oficial FUNVISIS; usando proxy USGS")
                    next_action = "reemplazar fallback cuando exista fuente oficial"
                elif availability_status == "available_raw":
                    next_action = "integrado desde Capa A"
                elif availability_status == "fixture_only":
                    gaps.append("falta catalogo raw real")
                    next_action = "sustituir fixture por catalogo oficial"
                else:
                    gaps.append("fuente no integrada")
            elif evidence_id == "EV-02" and accelerography_records:
                availability_status = "available_raw"
                data_mode = str(accelerography_payload.get("source", seismic.get("pga_measurement_quality", "estimated_shakemap")))
                record_count = len(accelerography_records)
                artifact_path = str(ACCELEROGRAPHY_RAW_PATH)
                supports_h04 = True
                if accelerography_payload.get("source") == "layer_c_accelerography_bootstrap":
                    gaps.append("dataset bootstrap derivado de ShakeMap; faltan registros instrumentales nativos")
                    next_action = "sustituir bootstrap con estaciones/acelerogramas reales cuando existan"
                else:
                    next_action = "integrado desde archivos raw por estacion"
            elif evidence_id == "EV-03" and geotech:
                availability_status = "partial"
                data_mode = "case_level_context_only"
                record_count = 1
                artifact_path = str(GEOTECHNICAL_NORMALIZED_PATH)
                supports_h04 = True
                gaps.append("no existe dataset geotecnico estructurado por sitio")
                next_action = "crear dataset por sitio con Vs30 y microzonificacion"
            elif evidence_id == "EV-04":
                gaps.append("no existe integracion satelital H04 en Capa C")
                next_action = "integrar InSAR y optico como evidencia del evento"
            elif evidence_id == "EV-05":
                gaps.append("no existe paquete estructurado de Cariaco 1997 en Capa C")
                next_action = "construir biblioteca comparativa historica"
            else:
                gaps.append("fuente no integrada")

            matrix.append({
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "source_name": source_name,
                "availability_status": availability_status,
                "data_mode": data_mode,
                "record_count": record_count,
                "artifact_path": artifact_path,
                "supports_h04": supports_h04,
                "gaps": gaps,
                "next_action": next_action,
            })
    return matrix


def _build_evidence_provenance_markdown(
    source_coverage: list[dict[str, Any]],
    accelerography_records: list[dict[str, Any]],
    geotechnical_records: list[dict[str, Any]],
    funvisis_connector: dict[str, Any],
) -> str:
    funvisis_status = "N/D"
    for row in source_coverage:
        if row.get("source_name") == "FUNVISIS":
            funvisis_status = str(row.get("connector_status", "N/D"))
            break

    lines = [
        "# Procedencia de Evidencia H04",
        "",
        "> **Estado destacado FUNVISIS:** "
        f"`{funvisis_status}` | estrategia `{funvisis_connector['status']}` | modo `{funvisis_connector['data_mode']}`",
        "",
        "## Catalogo sismico",
    ]
    for row in source_coverage:
        lines.append(
            f"- {row['source_name']}: estado={row['availability_status']}, modo={row['data_mode']}, procesados={row['processed_record_count']}"
        )
    lines.extend([
        "",
        "## FUNVISIS",
        f"- Estrategia actual: {funvisis_connector['status']}",
        f"- Modo: {funvisis_connector['data_mode']}",
        f"- Fuente utilizada: {funvisis_connector['source_reference']}",
        f"- Notas: {funvisis_connector['notes']}",
        "- Endpoint observado: https://www.funvisis.gob.ve/maravilla.json",
        "- Estructura observada: FeatureCollection tipo GeoJSON con eventos recientes.",
        "- Limitaciones: sin filtros documentados y cobertura historica aparente limitada.",
        "",
        "## Acelerografia",
        f"- Registros raw: {len(accelerography_records)}",
        f"- Archivo raw: {ACCELEROGRAPHY_RAW_PATH}",
        f"- Archivo normalizado: {ACCELEROGRAPHY_NORMALIZED_PATH}",
        "- Procedencia: archivo raw por estacion si existe; en ausencia de este, bootstrap desde pga_station_estimates y campos PGA/PGV del caso Venezuela 2026.",
        "",
        "## Geotecnia",
        f"- Registros normalizados: {len(geotechnical_records)}",
        f"- Archivo normalizado: {GEOTECHNICAL_NORMALIZED_PATH}",
        "- Procedencia: advanced_features.geological_geotechnical del caso Venezuela 2026.",
    ])
    return "\n".join(lines)


def _build_schema_reference_markdown() -> str:
    return "\n".join([
        "# Esquemas H04",
        "",
        "## Acelerografia",
        "- Archivo: layer_c_event_analysis/schemas/accelerography_record.schema.json",
        "- Campos clave: record_id, station_id, measurement_mode, pga_g, pgv_cm_per_s, site_class, provenance.",
        "",
        "## Geotecnia",
        "- Archivo: layer_c_event_analysis/schemas/geotechnical_site_record.schema.json",
        "- Campos clave: site_id, soil_type, lithology, vs30_m_per_s, sedimentary_basin, liquefaction_likelihood, provenance.",
    ])


def _build_external_source_registry(config: dict[str, Any]) -> list[dict[str, Any]]:
    registry = _external_source_registry_config(config)
    rows = registry.get("sources", []) if isinstance(registry, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _build_external_source_priorities(config: dict[str, Any]) -> list[dict[str, Any]]:
    registry = _external_source_registry_config(config)
    priority_tiers = registry.get("priority_tiers", {}) if isinstance(registry, dict) else {}
    rows: list[dict[str, Any]] = []
    for tier_name, sources in priority_tiers.items():
        if not isinstance(sources, list):
            continue
        for order, source_name in enumerate(sources, start=1):
            rows.append({
                "priority_tier": tier_name,
                "priority_rank": order,
                "source_name": str(source_name),
            })
    return rows


def _build_external_source_reference_markdown(
    config: dict[str, Any],
    registry_rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
) -> str:
    registry = _external_source_registry_config(config)
    lines = [
        "# Fuentes Externas H04",
        "",
        f"- Documento de referencia: {registry.get('reference_document', 'N/D')}",
        f"- Total de fuentes catalogadas: {len(registry_rows)}",
        "",
        "## Priorizacion",
    ]
    for row in priority_rows:
        lines.append(
            f"- {row['priority_tier']} #{row['priority_rank']}: {row['source_name']}"
        )

    lines.extend([
        "",
        "## Fuentes catalogadas",
    ])
    for row in registry_rows:
        usage = row.get("usage", [])
        usage_text = ", ".join(str(item) for item in usage) if isinstance(usage, list) else str(usage)
        lines.append(
            f"- {row.get('source_name', 'N/D')} | categoria={row.get('category', 'N/D')} | dominio={row.get('domain', 'N/D')} | layer={row.get('target_layer', 'N/D')} | prioridad={row.get('priority_level', 'N/D')} | uso={usage_text}"
        )
    return "\n".join(lines)


def _build_report(config: dict[str, Any], reference_excerpt: str) -> str:
    project = config["project"]
    event = config["event"]
    lines = [
        f"# {project['title']}",
        "",
        f"- Evento analizado: {event['name']}",
        f"- Fecha: {event['date_utc']}",
        f"- Enfoque: {project['analysis_scope']}",
        f"- Proyeccion: {'no' if not project['projection_mode'] else 'si'}",
        f"- Documento fuente: {config['reference']['document_path']}",
        "",
        "## Hipotesis principales",
    ]
    for row in config["hypotheses"]:
        lines.append(f"- {row['hypothesis_id']}: {row['statement']}")

    lines.extend([
        "",
        "## Lineas de evidencia requeridas",
    ])
    for row in config["evidence_lines"]:
        lines.append(
            f"- {row['evidence_id']}: {row['evidence_type']} | prioridad {row['priority']} | objetivo: {row['target']}"
        )

    lines.extend([
        "",
        "## Preguntas cientificas",
    ])
    for row in config["scientific_questions"]:
        lines.append(f"- {row['question_id']}: {row['question']}")

    lines.extend([
        "",
        "## Criterio de validacion",
        config["validation_criterion"],
        "",
        "## Extracto del documento de referencia",
        reference_excerpt,
    ])
    return "\n".join(lines)


def run_pipeline(config_path: Path | None = None) -> dict[str, Any]:
    _ensure_dirs()
    config = load_config(config_path)
    reference_text = REFERENCE_DOC.read_text(encoding="utf-8") if REFERENCE_DOC.exists() else "Documento no disponible."
    reference_excerpt = "\n".join(reference_text.splitlines()[:24])
    layer_a_summary = _load_layer_a_summary()
    event_case = _load_event_case()

    hypotheses_path = PROCESSED_DIR / "h04_hypotheses.json"
    evidence_path = PROCESSED_DIR / "h04_evidence_lines.json"
    questions_path = PROCESSED_DIR / "h04_scientific_questions.json"
    focus_path = PROCESSED_DIR / "h04_analysis_focus.json"
    catalog_coverage_path = PROCESSED_DIR / "h04_catalog_source_coverage.json"
    catalog_events_path = PROCESSED_DIR / "h04_catalog_event_candidates.json"
    coverage_matrix_path = PROCESSED_DIR / "h04_source_coverage_matrix.json"
    external_source_registry_path = PROCESSED_DIR / "h04_external_source_registry.json"
    external_source_priorities_path = PROCESSED_DIR / "h04_external_source_priorities.json"
    accelerography_raw_path = ACCELEROGRAPHY_RAW_PATH
    accelerography_normalized_path = ACCELEROGRAPHY_NORMALIZED_PATH
    geotechnical_normalized_path = GEOTECHNICAL_NORMALIZED_PATH
    evidence_provenance_path = REPORTS_DIR / "h04_evidence_provenance.md"
    schema_reference_path = REPORTS_DIR / "h04_schema_reference.md"
    external_source_reference_path = REPORTS_DIR / "h04_external_sources.md"
    summary_path = PROCESSED_DIR / "pipeline_summary.json"
    report_path = REPORTS_DIR / "reporte_h04_evento_venezuela_2026.md"

    catalog_source_coverage = _build_catalog_source_coverage(layer_a_summary)
    catalog_event_candidates = _build_catalog_event_candidates(config, layer_a_summary)
    external_source_registry = _build_external_source_registry(config)
    external_source_priorities = _build_external_source_priorities(config)
    accelerography_raw = _build_accelerography_raw_payload(event_case, config)
    accelerography_records = _normalize_accelerography_records(accelerography_raw)
    geotechnical_records = _build_geotechnical_site_records(event_case)
    funvisis_connector = _resolve_funvisis_connector(config, catalog_event_candidates, layer_a_summary)
    source_coverage_matrix = _build_source_coverage_matrix(
        config,
        catalog_source_coverage,
        event_case,
        accelerography_raw,
        accelerography_records,
        funvisis_connector,
    )

    focus_payload = {
        "analysis_scope": config["project"]["analysis_scope"],
        "projection_mode": config["project"]["projection_mode"],
        "event_id": config["event"]["event_id"],
        "reference_document": config["reference"]["document_path"],
        "core_components": config["analysis_axes"],
        "catalog_bridge": {
            "layer_a_summary_path": str(LAYER_A_SUMMARY_PATH),
            "catalog_sources_connected": ["USGS", "FUNVISIS"],
            "processed_catalog_path": str(LAYER_A_PROCESSED_DIR / "catalog_with_faults.parquet"),
            "funvisis_connector_status": funvisis_connector["status"],
        },
    }

    _write_json(hypotheses_path, config["hypotheses"])
    _write_json(evidence_path, config["evidence_lines"])
    _write_json(questions_path, config["scientific_questions"])
    _write_json(focus_path, focus_payload)
    _write_json(catalog_coverage_path, catalog_source_coverage)
    _write_json(catalog_events_path, catalog_event_candidates)
    _write_json(coverage_matrix_path, source_coverage_matrix)
    _write_json(external_source_registry_path, external_source_registry)
    _write_json(external_source_priorities_path, external_source_priorities)
    _write_json(accelerography_raw_path, accelerography_raw)
    _write_json(accelerography_normalized_path, accelerography_records)
    _write_json(geotechnical_normalized_path, geotechnical_records)
    evidence_provenance_path.write_text(
        _build_evidence_provenance_markdown(
            catalog_source_coverage,
            accelerography_records,
            geotechnical_records,
            funvisis_connector,
        ),
        encoding="utf-8",
    )
    schema_reference_path.write_text(_build_schema_reference_markdown(), encoding="utf-8")
    external_source_reference_path.write_text(
        _build_external_source_reference_markdown(
            config,
            external_source_registry,
            external_source_priorities,
        ),
        encoding="utf-8",
    )
    report_path.write_text(_build_report(config, reference_excerpt), encoding="utf-8")

    summary = {
        "layer": "C_event_h04",
        "title": config["project"]["title"],
        "analysis_scope": config["project"]["analysis_scope"],
        "projection_mode": config["project"]["projection_mode"],
        "event_id": config["event"]["event_id"],
        "event_name": config["event"]["name"],
        "reference_document": config["reference"]["document_path"],
        "hypotheses_defined": len(config["hypotheses"]),
        "evidence_lines_defined": len(config["evidence_lines"]),
        "scientific_questions_defined": len(config["scientific_questions"]),
        "catalog_sources_connected": len(catalog_source_coverage),
        "catalog_event_candidates": len(catalog_event_candidates),
        "external_sources_cataloged": len(external_source_registry),
        "external_source_priority_rows": len(external_source_priorities),
        "accelerography_records": len(accelerography_records),
        "geotechnical_records": len(geotechnical_records),
        "coverage_matrix_rows": len(source_coverage_matrix),
        "funvisis_connector_status": funvisis_connector["status"],
        "outputs": {
            "focus": str(focus_path),
            "hypotheses": str(hypotheses_path),
            "evidence_lines": str(evidence_path),
            "scientific_questions": str(questions_path),
            "catalog_source_coverage": str(catalog_coverage_path),
            "catalog_event_candidates": str(catalog_events_path),
            "source_coverage_matrix": str(coverage_matrix_path),
            "external_source_registry": str(external_source_registry_path),
            "external_source_priorities": str(external_source_priorities_path),
            "accelerography_raw": str(accelerography_raw_path),
            "accelerography_normalized": str(accelerography_normalized_path),
            "geotechnical_normalized": str(geotechnical_normalized_path),
            "evidence_provenance": str(evidence_provenance_path),
            "schema_reference": str(schema_reference_path),
            "external_source_reference": str(external_source_reference_path),
            "report": str(report_path),
        },
    }
    _write_json(summary_path, summary)

    artifacts = {
        "summary": summary_path,
        "focus": focus_path,
        "hypotheses": hypotheses_path,
        "evidence_lines": evidence_path,
        "scientific_questions": questions_path,
        "catalog_source_coverage": catalog_coverage_path,
        "catalog_event_candidates": catalog_events_path,
        "source_coverage_matrix": coverage_matrix_path,
        "external_source_registry": external_source_registry_path,
        "external_source_priorities": external_source_priorities_path,
        "accelerography_raw": accelerography_raw_path,
        "accelerography_normalized": accelerography_normalized_path,
        "geotechnical_normalized": geotechnical_normalized_path,
        "evidence_provenance": evidence_provenance_path,
        "schema_reference": schema_reference_path,
        "external_source_reference": external_source_reference_path,
        "report": report_path,
    }
    summary["persistence"] = persist_run(summary, artifacts)
    _write_json(summary_path, summary)
    return summary