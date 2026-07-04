"""Cliente FUNVISIS — descarga y normalizacion de eventos recientes."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from layer_a.paths import RAW_DIR


DEFAULT_FUNVISIS_ENDPOINT = "https://www.funvisis.gob.ve/maravilla.json"


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _parse_depth_km(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("km", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_datetime(date_str: Any, time_str: Any) -> str:
    date_text = str(date_str or "").strip()
    time_text = str(time_str or "00:00").strip()
    try:
        dt = datetime.strptime(f"{date_text} {time_text}", "%d-%m-%Y %H:%M")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return f"{date_text} {time_text}".strip()


def _build_event_id(dt_text: str, lat: float | None, lon: float | None, mag: float | None) -> str:
    seed = f"{dt_text}|{lat}|{lon}|{mag}".encode("utf-8")
    return f"funvisis_{hashlib.sha256(seed).hexdigest()[:16]}"


def _normalize_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    properties = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None

    coordinates = geometry.get("coordinates", [])
    lon = None
    lat = None
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        lon = _parse_float(coordinates[0])
        lat = _parse_float(coordinates[1])
    if lat is None:
        lat = _parse_float(properties.get("lat"))
    if lon is None:
        lon = _parse_float(properties.get("long"))

    magnitude = _parse_float(properties.get("value"))
    depth_km = _parse_depth_km(properties.get("depth"))
    datetime_utc = _parse_datetime(properties.get("date"), properties.get("time"))
    event_id = _build_event_id(datetime_utc, lat, lon, magnitude)

    return {
        "event_id": event_id,
        "source_event_id": event_id,
        "datetime_utc": datetime_utc,
        "latitude": lat,
        "longitude": lon,
        "depth_km": depth_km,
        "magnitude": magnitude,
        "magnitude_type": "Mw",
        "place": str(properties.get("addressFormatted", "")),
        "status": "reviewed",
        "location_uncertainty_km": None,
        "depth_uncertainty_km": None,
        "magnitude_uncertainty": None,
        "country": str(properties.get("country", "Venezuela")),
        "raw_properties": properties,
    }


def normalize_funvisis_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("type") == "FeatureCollection":
        features = payload.get("features", [])
        events: list[dict[str, Any]] = []
        if isinstance(features, list):
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                normalized = _normalize_feature(feature)
                if normalized is not None:
                    events.append(normalized)
        return {
            "source": "funvisis",
            "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_count": len(events),
            "events": events,
            "source_format": "feature_collection_recent_events",
            "historical_scope": "recent_events_only",
            "documented_filters": False,
            "endpoint": DEFAULT_FUNVISIS_ENDPOINT,
        }

    if isinstance(payload, dict):
        events = payload.get("events", payload.get("records", []))
        if isinstance(events, list):
            return {
                "source": str(payload.get("source", "funvisis")),
                "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_count": len(events),
                "events": events,
                "source_format": str(payload.get("source_format", "normalized_dump")),
                "historical_scope": str(payload.get("historical_scope", "unknown")),
                "documented_filters": bool(payload.get("documented_filters", False)),
                "endpoint": str(payload.get("endpoint", DEFAULT_FUNVISIS_ENDPOINT)),
            }

    return {
        "source": "funvisis",
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_count": 0,
        "events": [],
        "source_format": "unknown",
        "historical_scope": "unknown",
        "documented_filters": False,
        "endpoint": DEFAULT_FUNVISIS_ENDPOINT,
    }


def fetch_funvisis_payload(endpoint: str = DEFAULT_FUNVISIS_ENDPOINT, timeout_seconds: int = 20) -> Any:
    with urllib.request.urlopen(endpoint, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def save_funvisis_catalog(payload: dict[str, Any], path: Path | None = None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = path or RAW_DIR / "catalog_funvisis.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def download_and_save_funvisis(config: dict[str, Any]) -> tuple[Path, str]:
    endpoint = str(config.get("catalog", {}).get("endpoints", {}).get("funvisis", DEFAULT_FUNVISIS_ENDPOINT))
    payload = fetch_funvisis_payload(endpoint)
    normalized = normalize_funvisis_payload(payload)
    normalized["endpoint"] = endpoint
    path = save_funvisis_catalog(normalized)
    return path, f"ok (endpoint {normalized['event_count']} eventos)"