"""Cliente USGS FDSN — descarga catálogos a layer_a_tectonic/data/raw/."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from layer_a.formatting import format_datetime_utc
from layer_a.paths import RAW_DIR


def _mag_type_from_usgs(mag_type: str | None) -> str:
    if not mag_type:
        return "unknown"
    return mag_type


def _feature_to_event(feature: dict[str, Any]) -> dict[str, Any] | None:
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})
    if not isinstance(props, dict) or not isinstance(geom, dict):
        return None
    coords = geom.get("coordinates", [None, None, None])
    if len(coords) < 3:
        return None

    t_ms = props.get("time")
    if not isinstance(t_ms, (int, float)):
        return None
    dt = datetime.fromtimestamp(float(t_ms) / 1000.0, tz=timezone.utc)

    usgs_id = str(props.get("ids", props.get("code", ""))).split(",")[0].strip()
    if not usgs_id:
        usgs_id = str(int(t_ms))

    mag = props.get("mag")
    if mag is None:
        return None

    event_id = usgs_id if usgs_id.startswith("us") else f"usgs_{usgs_id}"

    return {
        "event_id": event_id,
        "source_event_id": usgs_id,
        "datetime_utc": format_datetime_utc(dt),
        "latitude": float(coords[1]),
        "longitude": float(coords[0]),
        "depth_km": abs(float(coords[2])),
        "magnitude": float(mag),
        "magnitude_type": _mag_type_from_usgs(props.get("magType")),
        "place": str(props.get("place", "")),
        "status": str(props.get("status", "reviewed")),
        "location_uncertainty_km": props.get("dmin"),
        "depth_uncertainty_km": props.get("depthError"),
        "magnitude_uncertainty": props.get("magError"),
    }


def download_usgs_catalog(
    *,
    start_date: date,
    end_date: date,
    min_magnitude: float,
    bbox: dict[str, float],
    timeout_seconds: int = 30,
) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, str | float] = {
        "format": "geojson",
        "starttime": start_date.isoformat(),
        "endtime": end_date.isoformat(),
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
        "limit": 20000,
        "minlatitude": bbox["min_lat"],
        "maxlatitude": bbox["max_lat"],
        "minlongitude": bbox["min_lon"],
        "maxlongitude": bbox["max_lon"],
    }
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout_seconds) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    events: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        event = _feature_to_event(feature)
        if event:
            events.append(event)

    status = f"ok ({len(events)} eventos)"
    return events, status


def save_usgs_catalog(events: list[dict[str, Any]], path: Path | None = None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = path or RAW_DIR / "catalog_usgs.json"
    payload = {
        "source": "usgs",
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_count": len(events),
        "events": events,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def download_and_save_usgs(
    config: dict[str, Any],
    *,
    end_date: date | None = None,
) -> tuple[Path, str]:
    project = config["project"]
    catalog_cfg = config["catalog"]
    region = config["region"]["bbox"]

    start = date.fromisoformat(project["start_date"])
    end = end_date or date.today()

    events, status = download_usgs_catalog(
        start_date=start,
        end_date=end,
        min_magnitude=float(catalog_cfg["min_magnitude"]),
        bbox=region,
    )
    path = save_usgs_catalog(events)
    return path, status
