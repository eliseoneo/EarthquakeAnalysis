"""Cliente INGV — descarga catalogos a layer_a_tectonic/data/raw/."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from layer_a.formatting import format_datetime_utc
from layer_a.paths import RAW_DIR


def _mag_type_from_ingv(mag_type: str | None) -> str:
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

    time_str = props.get("time") or props.get("origin_time")
    if not isinstance(time_str, str):
        return None
    t = time_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)

    mag = props.get("mag")
    if mag is None:
        return None

    source_event_id = str(props.get("eventid", feature.get("id", ""))).strip()
    if not source_event_id:
        source_event_id = dt.strftime("%Y%m%d%H%M%S")

    event_id = source_event_id if source_event_id.startswith("ingv_") else f"ingv_{source_event_id}"

    return {
        "event_id": event_id,
        "source_event_id": source_event_id,
        "datetime_utc": format_datetime_utc(dt),
        "latitude": float(coords[1]),
        "longitude": float(coords[0]),
        "depth_km": abs(float(coords[2])),
        "magnitude": float(mag),
        "magnitude_type": _mag_type_from_ingv(str(props.get("magType", "unknown"))),
        "place": str(props.get("place", "")),
        "status": str(props.get("status", "reviewed")),
        "location_uncertainty_km": props.get("horizontalError"),
        "depth_uncertainty_km": props.get("depthError"),
        "magnitude_uncertainty": props.get("magError"),
    }


def _safe_text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def _first(root: ET.Element, path: str, ns: dict[str, str]) -> ET.Element | None:
    return root.find(path, ns)


def _quakeml_event_to_dict(event_el: ET.Element, ns: dict[str, str]) -> dict[str, Any] | None:
    public_id = event_el.get("publicID", "")
    source_event_id = public_id.rsplit("/", 1)[-1] if public_id else ""

    desc = _first(event_el, "q:description/q:text", ns)
    place = _safe_text(desc) or ""

    origin = _first(event_el, "q:origin", ns)
    magnitude = _first(event_el, "q:magnitude", ns)
    if origin is None or magnitude is None:
        return None

    t_el = _first(origin, "q:time/q:value", ns)
    lat_el = _first(origin, "q:latitude/q:value", ns)
    lon_el = _first(origin, "q:longitude/q:value", ns)
    dep_el = _first(origin, "q:depth/q:value", ns)
    mag_el = _first(magnitude, "q:mag/q:value", ns)
    mag_type_el = _first(magnitude, "q:type", ns)

    if any(x is None for x in (t_el, lat_el, lon_el, dep_el, mag_el)):
        return None

    t_txt = _safe_text(t_el)
    lat_txt = _safe_text(lat_el)
    lon_txt = _safe_text(lon_el)
    dep_txt = _safe_text(dep_el)
    mag_txt = _safe_text(mag_el)
    if any(x is None for x in (t_txt, lat_txt, lon_txt, dep_txt, mag_txt)):
        return None

    dt = datetime.fromisoformat(t_txt.replace("Z", "+00:00"))
    depth_raw = float(dep_txt)
    depth_km = depth_raw / 1000.0 if abs(depth_raw) > 1000.0 else depth_raw

    if not source_event_id:
        source_event_id = dt.strftime("%Y%m%d%H%M%S")

    return {
        "event_id": f"ingv_{source_event_id}",
        "source_event_id": source_event_id,
        "datetime_utc": format_datetime_utc(dt),
        "latitude": float(lat_txt),
        "longitude": float(lon_txt),
        "depth_km": abs(depth_km),
        "magnitude": float(mag_txt),
        "magnitude_type": _mag_type_from_ingv(_safe_text(mag_type_el)),
        "place": place,
        "status": "reviewed",
        "location_uncertainty_km": None,
        "depth_uncertainty_km": None,
        "magnitude_uncertainty": None,
    }


def _parse_quakeml_events(xml_bytes: bytes) -> list[dict[str, Any]]:
    ns = {
        "q": "http://quakeml.org/xmlns/bed/1.2",
    }
    root = ET.fromstring(xml_bytes.lstrip())
    events = root.findall(".//q:event", ns)

    parsed: list[dict[str, Any]] = []
    for event in events:
        out = _quakeml_event_to_dict(event, ns)
        if out is not None:
            parsed.append(out)
    return parsed


def _parse_payload(payload: bytes) -> list[dict[str, Any]]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _parse_quakeml_events(payload)

    if isinstance(data, dict) and isinstance(data.get("features"), list):
        events: list[dict[str, Any]] = []
        for feature in data["features"]:
            if not isinstance(feature, dict):
                continue
            event = _feature_to_event(feature)
            if event:
                events.append(event)
        return events
    return []


def download_ingv_catalog(
    *,
    start_date: date,
    end_date: date,
    min_magnitude: float,
    bbox: dict[str, float],
    endpoint: str = "https://webservices.ingv.it/fdsnws/event/1/query",
    timeout_seconds: int = 45,
) -> tuple[list[dict[str, Any]], str]:
    params: dict[str, str | float] = {
        "starttime": start_date.isoformat(),
        "endtime": end_date.isoformat(),
        "minmagnitude": min_magnitude,
        "minlatitude": bbox["min_lat"],
        "maxlatitude": bbox["max_lat"],
        "minlongitude": bbox["min_lon"],
        "maxlongitude": bbox["max_lon"],
        "orderby": "time-asc",
        # Se solicita GeoJSON; si no es soportado, _parse_payload intenta QuakeML.
        "format": "geojson",
    }
    url = endpoint + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "EarthquakeAnalysis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        payload = resp.read()

    events = _parse_payload(payload)
    status = f"ok ({len(events)} eventos)"
    return events, status


def save_ingv_catalog(events: list[dict[str, Any]], path: Path | None = None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = path or RAW_DIR / "catalog_ingv.json"
    payload = {
        "source": "ingv",
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_count": len(events),
        "events": events,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def download_and_save_ingv(
    config: dict[str, Any],
    *,
    end_date: date | None = None,
) -> tuple[Path, str]:
    project = config["project"]
    catalog_cfg = config["catalog"]
    region = config["region"]["bbox"]

    endpoints = catalog_cfg.get("endpoints", {}) if isinstance(catalog_cfg, dict) else {}
    endpoint = str(endpoints.get("ingv", "https://webservices.ingv.it/fdsnws/event/1/query"))

    start = date.fromisoformat(project["start_date"])
    end = end_date or date.today()

    events, status = download_ingv_catalog(
        start_date=start,
        end_date=end,
        min_magnitude=float(catalog_cfg["min_magnitude"]),
        bbox=region,
        endpoint=endpoint,
    )
    path = save_ingv_catalog(events)
    return path, status
