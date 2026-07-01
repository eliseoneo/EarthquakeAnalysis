"""Cliente SGC — descarga catalogos a layer_a_tectonic/data/raw/."""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from layer_a.formatting import format_datetime_utc
from layer_a.paths import RAW_DIR

_DETAIL_PATTERN = re.compile(r"/detallesismo/([A-Za-z0-9_\-]+)/resumen")


def _http_get(url: str, timeout_seconds: int) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "EarthquakeAnalysis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "EarthquakeAnalysis/1.0",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(html: str) -> str:
    no_script = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    no_style = re.sub(r"<style.*?>.*?</style>", " ", no_script, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", no_style)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_event_ids_from_sismos_html(html: str, max_events: int) -> list[str]:
    found = _DETAIL_PATTERN.findall(html)
    unique: list[str] = []
    seen: set[str] = set()
    for event_id in found:
        if event_id in seen:
            continue
        seen.add(event_id)
        unique.append(event_id)
        if len(unique) >= max_events:
            break
    return unique


def _parse_time_utc(text: str) -> datetime | None:
    match_utc = re.search(r"\((\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s*UTC\)", text)
    if match_utc:
        raw = match_utc.group(1)
        fmt = "%Y-%m-%d %H:%M:%S" if len(raw) == 19 else "%Y-%m-%d %H:%M"
        dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        return dt

    # Fallback: hora local Colombia (UTC-5) cuando no viene UTC explicito.
    match_local = re.search(r"Tiempo de origen:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)\s*Hora local", text)
    if not match_local:
        return None
    raw = match_local.group(1)
    fmt = "%Y-%m-%d %H:%M:%S" if len(raw) == 19 else "%Y-%m-%d %H:%M"
    local_dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
    return local_dt + timedelta(hours=5)


def _parse_depth_km(text: str) -> float | None:
    depth_match = re.search(r"Profundidad:\s*(Superficial|[0-9]+(?:\.[0-9]+)?\s*km)", text, re.IGNORECASE)
    if not depth_match:
        return None
    value = depth_match.group(1).strip().lower()
    if value == "superficial":
        return 10.0
    km_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", value)
    return float(km_match.group(1)) if km_match else None


def _parse_magnitude(text: str) -> float | None:
    # Patrn prioritario para paginas de detalle.
    mag_patterns = [
        r"Magnitud\s*:?\s*([0-9]+(?:\.[0-9]+)?)",
        r"\bM\s*:?\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in mag_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def _parse_location(text: str) -> tuple[float | None, float | None]:
    loc = re.search(r"Localizaci[oó]n:\s*([+-]?\d+(?:\.\d+)?)°\s*,\s*([+-]?\d+(?:\.\d+)?)°", text)
    if not loc:
        return None, None
    return float(loc.group(1)), float(loc.group(2))


def _parse_place(text: str) -> str:
    # Se usa "Municipios cercanos" o nombre de localidad si aparece.
    near = re.search(r"Municipios cercanos:\s*([^\.]+)", text)
    if near:
        return near.group(1).strip()
    return ""


def _parse_agency(text: str) -> str:
    agency = re.search(r"Agencia:\s*([A-Za-z0-9]+)", text)
    if agency:
        return agency.group(1).upper()
    return "SGC"


def _parse_sgc_detail_page(html: str, event_id: str) -> dict[str, Any] | None:
    text = _strip_html(html)
    dt = _parse_time_utc(text)
    magnitude = _parse_magnitude(text)
    lat, lon = _parse_location(text)
    depth_km = _parse_depth_km(text)

    if dt is None or magnitude is None or lat is None or lon is None or depth_km is None:
        return None

    place = _parse_place(text)
    agency = _parse_agency(text)

    return {
        "event_id": f"sgc_{event_id}",
        "source_event_id": event_id,
        "datetime_utc": format_datetime_utc(dt),
        "latitude": lat,
        "longitude": lon,
        "depth_km": depth_km,
        "magnitude": magnitude,
        "magnitude_type": "M",
        "place": place,
        "status": "reviewed" if agency == "SGC" else "automatic",
        "location_uncertainty_km": None,
        "depth_uncertainty_km": None,
        "magnitude_uncertainty": None,
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        if text == "superficial":
            return 10.0
        match = re.search(r"([+-]?\d+(?:\.\d+)?)", text)
        if match:
            return float(match.group(1))
    return None


def _parse_sgc_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("T", " ").replace("Z", "")
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return dt


def _api_row_to_event(row: dict[str, Any]) -> dict[str, Any] | None:
    source_event_id = str(row.get("id", "")).strip()
    if not source_event_id:
        return None

    dt = _parse_sgc_utc(row.get("utc_time"))
    mag = _safe_float(row.get("magnitude"))
    lat = _safe_float(row.get("latitude"))
    lon = _safe_float(row.get("longitude"))
    depth = _safe_float(row.get("depth"))
    if dt is None or mag is None or lat is None or lon is None or depth is None:
        return None

    lat_err = _safe_float(row.get("latitude_error"))
    lon_err = _safe_float(row.get("longitude_error"))
    loc_err = None
    if lat_err is not None and lon_err is not None:
        loc_err = (abs(lat_err) + abs(lon_err)) / 2.0
    elif lat_err is not None:
        loc_err = abs(lat_err)
    elif lon_err is not None:
        loc_err = abs(lon_err)

    return {
        "event_id": f"sgc_{source_event_id}",
        "source_event_id": source_event_id,
        "datetime_utc": format_datetime_utc(dt),
        "latitude": lat,
        "longitude": lon,
        "depth_km": abs(depth),
        "magnitude": mag,
        "magnitude_type": str(row.get("mag_type", "M") or "M"),
        "place": str(row.get("place", "") or ""),
        "status": str(row.get("status", "reviewed") or "reviewed"),
        "location_uncertainty_km": loc_err,
        "depth_uncertainty_km": _safe_float(row.get("depth_error")),
        "magnitude_uncertainty": _safe_float(row.get("magnitude_error")),
    }


def download_sgc_catalog(
    *,
    start_date: date,
    end_date: date,
    max_events: int = 120,
    search_url: str = "https://apicatalogador.sgc.gov.co/api/events/search/",
    list_url: str = "https://www.sgc.gov.co/sismos",
    detail_url_template: str = "https://www.sgc.gov.co/detallesismo/{event_id}/resumen",
    timeout_seconds: int = 45,
) -> tuple[list[dict[str, Any]], str]:
    start_ts = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_ts = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    events: list[dict[str, Any]] = []
    failed = 0

    # Ruta principal: API oficial de catalogador (JSON paginado).
    try:
        payload: dict[str, Any] = {
            "page_size": min(500, max_events),
        }
        next_url: str | None = search_url
        while next_url and len(events) < max_events:
            response = _http_post_json(next_url, payload, timeout_seconds)
            results_node = response.get("results", {}) if isinstance(response, dict) else {}
            rows = results_node.get("results", []) if isinstance(results_node, dict) else []

            if not isinstance(rows, list):
                break

            for row in rows:
                if not isinstance(row, dict):
                    continue
                event = _api_row_to_event(row)
                if event is None:
                    failed += 1
                    continue

                event_dt = datetime.strptime(event["datetime_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if not (start_ts <= event_dt <= end_ts):
                    continue

                events.append(event)
                if len(events) >= max_events:
                    break

            maybe_next = response.get("next") if isinstance(response, dict) else None
            next_url = str(maybe_next) if isinstance(maybe_next, str) and maybe_next else None

        if events:
            status = f"ok ({len(events)} eventos API, {failed} descartados)"
            return events, status
    except (HTTPError, ValueError, KeyError):
        # Continua con fallback HTML.
        pass

    # Fallback: scraping HTML si la API no devuelve resultados.
    list_html = _http_get(list_url, timeout_seconds)
    event_ids = _extract_event_ids_from_sismos_html(list_html, max_events=max_events)

    for event_id in event_ids:
        detail_url = detail_url_template.format(event_id=event_id)
        try:
            detail_html = _http_get(detail_url, timeout_seconds)
            event = _parse_sgc_detail_page(detail_html, event_id)
            if event is not None:
                events.append(event)
            else:
                failed += 1
        except Exception:
            failed += 1

    status = f"ok ({len(events)} eventos, {failed} descartados)"
    return events, status


def save_sgc_catalog(events: list[dict[str, Any]], path: Path | None = None) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = path or RAW_DIR / "catalog_sgc.json"
    payload = {
        "source": "sgc",
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_count": len(events),
        "events": events,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def download_and_save_sgc(
    config: dict[str, Any],
    *,
    end_date: date | None = None,
) -> tuple[Path, str]:
    project = config["project"]
    catalog_cfg = config["catalog"]

    endpoints = catalog_cfg.get("endpoints", {}) if isinstance(catalog_cfg, dict) else {}
    search_url = str(endpoints.get("sgc_search", "https://apicatalogador.sgc.gov.co/api/events/search/"))
    list_url = str(endpoints.get("sgc_list", "https://www.sgc.gov.co/sismos"))
    detail_tpl = str(endpoints.get("sgc_detail", "https://www.sgc.gov.co/detallesismo/{event_id}/resumen"))

    start = date.fromisoformat(project["start_date"])
    end = end_date or date.today()

    events, status = download_sgc_catalog(
        start_date=start,
        end_date=end,
        max_events=int(catalog_cfg.get("sgc_max_events", 120)),
        search_url=search_url,
        list_url=list_url,
        detail_url_template=detail_tpl,
    )
    path = save_sgc_catalog(events)
    return path, status
