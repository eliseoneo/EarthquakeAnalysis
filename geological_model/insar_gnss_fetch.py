"""Obtención de InSAR/GNSS medidos y reemplazo de filas proxy."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from geological_model.insar_bridge import (
    INSAR_GNSS_HEADERS,
    STATUS_MEASURED,
    STATUS_PROXY,
    build_geological_insar_bridge_summary,
    build_insar_gnss_rows,
)
from geological_model.paths import (
    FIXTURES_DIR,
    INSAR_GNSS_CONFIG,
    MEASURED_WINDOWS_FILE,
    RAW_DIR,
    REPO_ROOT,
)


@dataclass(frozen=True)
class GnssStationVelocity:
    station_id: str
    latitude: float
    longitude: float
    east_m_per_year: float
    north_m_per_year: float
    up_m_per_year: float
    start_decimal_year: float
    end_decimal_year: float

    @property
    def vsr_mm_per_year(self) -> float:
        return abs(self.up_m_per_year) * 1000.0

    @property
    def ssr_mm_per_year(self) -> float:
        horizontal = math.hypot(self.east_m_per_year, self.north_m_per_year)
        return horizontal * 1000.0

    @property
    def nsr_mm_per_year(self) -> float:
        return math.hypot(self.vsr_mm_per_year, self.ssr_mm_per_year)

    def active_in_window(self, window_start: date, window_end: date) -> bool:
        start_y = _date_to_decimal_year(window_start)
        end_y = _date_to_decimal_year(window_end)
        return self.end_decimal_year >= start_y and self.start_decimal_year <= end_y


def load_insar_gnss_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or INSAR_GNSS_CONFIG
    with config_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class WindowStub:
    start_date: date
    end_date: date
    features: dict[str, float]


def window_stubs_from_rows(
    rows: Sequence[Sequence[Any]],
) -> list[WindowStub]:
    stubs: list[WindowStub] = []
    for row in rows:
        if len(row) < 2:
            continue
        start = _parse_iso_date(row[0])
        end = _parse_iso_date(row[1])
        if start is None or end is None:
            continue
        stubs.append(WindowStub(start_date=start, end_date=end, features={}))
    return stubs


def fetch_and_replace_from_international_payload(
    payload: dict[str, Any],
    *,
    use_live: bool = True,
    local_measured_path: Path | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[list[str | float | None]], dict[str, Any]]:
    """Reemplaza insar_gnss_rows de un payload internacional con mediciones GNSS."""
    proxy_rows = payload.get("insar_gnss_rows")
    if not isinstance(proxy_rows, list):
        raise ValueError("Payload internacional sin insar_gnss_rows")
    stubs = window_stubs_from_rows(proxy_rows)
    return fetch_and_replace_insar_gnss_rows(
        stubs,
        proxy_rows=proxy_rows,
        use_live=use_live,
        local_measured_path=local_measured_path,
        config=config,
        max_rows=len(proxy_rows),
    )


def fetch_and_replace_insar_gnss_rows(
    samples: Sequence[Any],
    *,
    proxy_rows: list[list[str | float | None]] | None = None,
    use_live: bool = True,
    local_measured_path: Path | None = None,
    config: dict[str, Any] | None = None,
    max_rows: int = 12,
) -> tuple[list[list[str | float | None]], dict[str, Any]]:
    """
    Obtiene tasas VSR/SSR/NSR medidas y reemplaza filas proxy del workflow internacional.

    Prioridad de fuentes:
    1. Archivo local de ventanas medidas (`local_measured_path` o raw del repo).
    2. Descarga GNSS MIDAS (NGL) + agregación por ventana.
    3. Conservar fila proxy si no hay medición disponible.
    """
    cfg = config or load_insar_gnss_config()
    base_rows = proxy_rows or build_insar_gnss_rows(samples, max_rows=max_rows)
    measured_rows, fetch_meta = fetch_measured_insar_gnss_rows(
        samples,
        use_live=use_live,
        local_measured_path=local_measured_path,
        config=cfg,
        max_rows=max_rows,
    )
    replaced_rows, replace_meta = replace_insar_gnss_rows(base_rows, measured_rows)
    metadata = {
        **fetch_meta,
        **replace_meta,
        "rows_total": len(replaced_rows),
    }
    return replaced_rows, metadata


def fetch_measured_insar_gnss_rows(
    samples: Sequence[Any],
    *,
    use_live: bool = True,
    local_measured_path: Path | None = None,
    config: dict[str, Any] | None = None,
    max_rows: int = 12,
) -> tuple[list[list[str | float | None]], dict[str, Any]]:
    """Obtiene filas medidas por ventana temporal."""
    cfg = config or load_insar_gnss_config()
    measured_path = local_measured_path or _resolve_measured_path(cfg)
    if measured_path.exists():
        rows = load_measured_rows_from_file(measured_path)
        return rows[-max_rows:], {
            "fetch_status": "loaded_local",
            "fetch_source": str(measured_path),
            "measured_rows": len(rows),
        }

    if not use_live:
        return [], {"fetch_status": "skipped", "fetch_source": None, "measured_rows": 0}

    stations, station_meta = fetch_ngl_midas_stations(cfg, use_cache=True)
    rows = build_measured_rows_from_stations(samples, stations, cfg, max_rows=max_rows)
    if rows:
        persist_measured_rows(rows, measured_path)
    return rows, {
        "fetch_status": station_meta.get("status", "live"),
        "fetch_source": station_meta.get("source"),
        "stations_in_bbox": station_meta.get("stations_in_bbox", 0),
        "measured_rows": len(rows),
    }


def replace_insar_gnss_rows(
    proxy_rows: Sequence[Sequence[Any]],
    measured_rows: Sequence[Sequence[Any]],
) -> tuple[list[list[str | float | None]], dict[str, Any]]:
    """Reemplaza filas proxy cuando existe una medición para la misma ventana."""
    measured_by_window = {
        (str(row[0]), str(row[1])): list(row)
        for row in measured_rows
        if len(row) >= len(INSAR_GNSS_HEADERS)
    }
    replaced: list[list[str | float | None]] = []
    replaced_count = 0
    for row in proxy_rows:
        key = (str(row[0]), str(row[1]))
        if key in measured_by_window and measured_by_window[key][5] == STATUS_MEASURED:
            replaced.append(measured_by_window[key])
            replaced_count += 1
            continue
        replaced.append(list(row))
    return replaced, {
        "replace_status": "completed",
        "rows_replaced": replaced_count,
        "rows_proxy_kept": len(replaced) - replaced_count,
    }


def load_measured_rows_from_file(path: Path) -> list[list[str | float | None]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("windows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"Expected list of windows in {path}")
    normalized: list[list[str | float | None]] = []
    for row in rows:
        if isinstance(row, list) and len(row) >= len(INSAR_GNSS_HEADERS):
            normalized.append(list(row))
    return normalized


def persist_measured_rows(
    rows: Sequence[Sequence[Any]],
    path: Path | None = None,
) -> Path:
    out_path = path or MEASURED_WINDOWS_FILE
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": "ngl_midas_igs14",
        "saved_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "windows": [list(row) for row in rows],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def find_international_payload_for_date(root: Path, as_of_date: date) -> Path | None:
    day_dir = (
        root
        / "storage"
        / "venezuela"
        / "international"
        / f"{as_of_date.year:04d}"
        / f"{as_of_date.month:02d}"
        / f"{as_of_date.day:02d}"
    )
    if not day_dir.exists():
        return None
    files = sorted(day_dir.glob("international_estimation_*.json"))
    return files[-1] if files else None


def apply_insar_replacement_to_payload(
    payload: dict[str, Any],
    replaced_rows: Sequence[Sequence[Any]],
    fetch_replace_meta: dict[str, Any],
) -> dict[str, Any]:
    """Actualiza campos InSAR/GNSS de un payload internacional ya reemplazado."""
    rows = [list(row) for row in replaced_rows]
    measured_count = sum(
        1 for row in rows if len(row) > 5 and row[5] == STATUS_MEASURED
    )
    proxy_count = len(rows) - measured_count
    bridge_payload = {"insar_gnss_rows": rows}

    updated = dict(payload)
    updated["insar_gnss_rows"] = rows
    updated["insar_fetch_meta"] = {
        "enabled": True,
        "measured_rows": measured_count,
        "proxy_rows": proxy_count,
        **fetch_replace_meta,
    }
    updated["insar_gnss_placeholder_policy"] = {
        "fields": ["vsr_mm_per_year", "ssr_mm_per_year", "nsr_mm_per_year"],
        "status": STATUS_MEASURED if measured_count else STATUS_PROXY,
        "notes": (
            "Filas InSAR/GNSS actualizadas con mediciones GNSS MIDAS (NGL)."
            if measured_count
            else "Sin mediciones disponibles; se conservan filas proxy."
        ),
    }
    updated["geological_insar_bridge"] = build_geological_insar_bridge_summary(bridge_payload)
    updated["insar_updated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return updated


def persist_international_payload(path: Path, payload: dict[str, Any]) -> Path:
    """Guarda payload internacional con filas InSAR/GNSS ya reemplazadas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def fetch_and_replace_international_payload_file(
    international_path: Path,
    *,
    use_live: bool = True,
    local_measured_path: Path | None = None,
    update_file: bool = True,
) -> tuple[Path, list[list[str | float | None]], dict[str, Any]]:
    """Obtiene mediciones, reemplaza filas y opcionalmente persiste el JSON internacional."""
    payload = json.loads(international_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping at root of {international_path}")

    replaced_rows, fetch_replace_meta = fetch_and_replace_from_international_payload(
        payload,
        use_live=use_live,
        local_measured_path=local_measured_path,
    )
    if update_file:
        updated = apply_insar_replacement_to_payload(payload, replaced_rows, fetch_replace_meta)
        persist_international_payload(international_path, updated)

    return international_path, replaced_rows, fetch_replace_meta


def fetch_ngl_midas_stations(
    config: dict[str, Any] | None = None,
    *,
    use_cache: bool = True,
) -> tuple[list[GnssStationVelocity], dict[str, Any]]:
    """Descarga estaciones GNSS MIDAS (NGL) dentro del bbox configurado."""
    cfg = config or load_insar_gnss_config()
    provider = cfg["providers"]["ngl_midas_igs14"]
    bbox = cfg["region"]["bbox"]
    cache_path = RAW_DIR / provider["cache_filename"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    text = ""
    source = provider["url"]
    status = "live"
    if use_cache and cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
        source = str(cache_path)
        status = "cache"
    else:
        try:
            text = _download_text(provider["url"], timeout=int(provider.get("timeout_seconds", 45)))
            cache_path.write_text(text, encoding="utf-8")
        except (OSError, urllib.error.URLError) as exc:
            fixture = FIXTURES_DIR / provider["cache_filename"]
            if fixture.exists():
                text = fixture.read_text(encoding="utf-8")
                source = str(fixture)
                status = "fixture_fallback"
            else:
                return [], {
                    "status": "failed",
                    "source": provider["url"],
                    "error": str(exc),
                    "stations_in_bbox": 0,
                }

    stations = parse_midas_velocity_text(text, bbox=bbox)
    return stations, {
        "status": status,
        "source": source,
        "stations_in_bbox": len(stations),
    }


def parse_midas_velocity_text(
    text: str,
    *,
    bbox: dict[str, float],
) -> list[GnssStationVelocity]:
    stations: list[GnssStationVelocity] = []
    for line in text.splitlines():
        parsed = parse_midas_velocity_line(line)
        if parsed is None:
            continue
        if not _in_bbox(parsed.latitude, parsed.longitude, bbox):
            continue
        stations.append(parsed)
    return stations


def parse_midas_velocity_line(line: str) -> GnssStationVelocity | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split()
    if len(parts) < 27:
        return None
    try:
        east = float(parts[8])
        north = float(parts[9])
        up = float(parts[10])
        latitude = float(parts[24])
        longitude = float(parts[25])
        if max(abs(east), abs(north), abs(up)) > 0.5:
            return None
        return GnssStationVelocity(
            station_id=parts[0],
            start_decimal_year=float(parts[2]),
            end_decimal_year=float(parts[3]),
            east_m_per_year=east,
            north_m_per_year=north,
            up_m_per_year=up,
            latitude=latitude,
            longitude=longitude,
        )
    except ValueError:
        return None


def build_measured_rows_from_stations(
    samples: Sequence[Any],
    stations: Sequence[GnssStationVelocity],
    config: dict[str, Any] | None = None,
    *,
    max_rows: int = 12,
) -> list[list[str | float | None]]:
    cfg = config or load_insar_gnss_config()
    min_stations = int(cfg.get("aggregation", {}).get("min_stations", 1))
    provider = cfg["providers"]["ngl_midas_igs14"]
    rows: list[list[str | float | None]] = []

    for sample in samples[-max_rows:]:
        start = getattr(sample, "start_date", None)
        end = getattr(sample, "end_date", None)
        if not isinstance(start, date) or not isinstance(end, date):
            continue

        active = [st for st in stations if st.active_in_window(start, end)]
        fallback = False
        if len(active) < min_stations:
            active = list(stations)
            fallback = True
        if len(active) < min_stations:
            continue

        vsr = sum(st.vsr_mm_per_year for st in active) / len(active)
        ssr = sum(st.ssr_mm_per_year for st in active) / len(active)
        nsr = sum(st.nsr_mm_per_year for st in active) / len(active)
        note_prefix = "GNSS MIDAS medido"
        if fallback:
            note_prefix = "GNSS MIDAS medido (campo regional"
        rows.append(
            [
                start.isoformat(),
                end.isoformat(),
                round(vsr, 4),
                round(ssr, 4),
                round(nsr, 4),
                STATUS_MEASURED,
                (
                    f"{note_prefix} ({provider['source_label']}): "
                    f"{len(active)} estaciones en bbox Venezuela-Caribe."
                    + (")" if fallback else ".")
                ),
            ]
        )
    return rows


def _resolve_measured_path(config: dict[str, Any]) -> Path:
    configured = config.get("paths", {}).get("measured_windows_file")
    if isinstance(configured, str):
        path = Path(configured)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path
    return MEASURED_WINDOWS_FILE


def _download_text(url: str, *, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "EarthquakeAnalysis/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def _in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def _date_to_decimal_year(value: date) -> float:
    day_of_year = value.timetuple().tm_yday
    return value.year + (day_of_year - 1) / 365.25
