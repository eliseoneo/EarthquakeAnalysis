"""Puente InSAR/GNSS entre workflow internacional y FCN geológico."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

INSAR_GNSS_HEADERS = [
    "window_start",
    "window_end",
    "vsr_mm_per_year",
    "ssr_mm_per_year",
    "nsr_mm_per_year",
    "data_status",
    "notes",
]

STATUS_MEASURED = "measured"
STATUS_PROXY = "proxy_from_seismic_catalog"
STATUS_PENDING = "placeholder_pending_source"


@dataclass(frozen=True)
class InsarGnssObservation:
    window_start: date
    window_end: date
    vsr_mm_per_year: float | None
    ssr_mm_per_year: float | None
    nsr_mm_per_year: float | None
    data_status: str
    notes: str

    @property
    def window_days(self) -> int:
        return max(1, (self.window_end - self.window_start).days + 1)

    def displacement_cm(self) -> float | None:
        if self.vsr_mm_per_year is None and self.ssr_mm_per_year is None and self.nsr_mm_per_year is None:
            return None
        vsr = self.vsr_mm_per_year or 0.0
        ssr = self.ssr_mm_per_year or 0.0
        nsr = self.nsr_mm_per_year or 0.0
        rate_mag = (vsr * vsr + ssr * ssr + nsr * nsr) ** 0.5
        displacement_mm = rate_mag * (self.window_days / 365.25)
        return round(displacement_mm / 10.0, 4)

    def insar_quality(self) -> str:
        if self.data_status == STATUS_MEASURED:
            return "instrumented_insar"
        if self.data_status == STATUS_PROXY:
            return "proxy_seismic_catalog"
        return "unknown"


def proxy_rates_from_window_features(features: dict[str, float]) -> tuple[float, float, float]:
    """Deriva VSR/SSR/NSR proxy desde features sísmicos de ventana internacional."""
    benioff = float(features.get("benioff_rate", 0.0))
    delta_m = float(features.get("delta_m", 0.0))
    m_mean = float(features.get("m_mean", 0.0))
    vsr = min(15.0, max(0.0, benioff * 0.05))
    ssr = min(12.0, max(0.0, delta_m * 3.0))
    nsr = min(10.0, max(0.0, m_mean * 0.9))
    return round(vsr, 4), round(ssr, 4), round(nsr, 4)


def build_insar_gnss_rows(
    samples: Sequence[Any],
    *,
    max_rows: int = 12,
    use_measured: bool = False,
    use_live: bool = True,
    local_measured_path: Path | None = None,
) -> list[list[str | float | None]]:
    """Construye filas InSAR/GNSS conectables al FCN geológico."""
    proxy_rows = _build_proxy_insar_gnss_rows(samples, max_rows=max_rows)
    if not use_measured:
        return proxy_rows

    from geological_model.insar_gnss_fetch import fetch_and_replace_insar_gnss_rows

    replaced_rows, _meta = fetch_and_replace_insar_gnss_rows(
        samples,
        proxy_rows=proxy_rows,
        use_live=use_live,
        local_measured_path=local_measured_path,
        max_rows=max_rows,
    )
    return replaced_rows


def _build_proxy_insar_gnss_rows(
    samples: Sequence[Any],
    *,
    max_rows: int = 12,
) -> list[list[str | float | None]]:
    rows: list[list[str | float | None]] = []
    for sample in samples[-max_rows:]:
        start = getattr(sample, "start_date", None)
        end = getattr(sample, "end_date", None)
        features = getattr(sample, "features", None)
        if not isinstance(start, date) or not isinstance(end, date) or not isinstance(features, dict):
            continue

        vsr, ssr, nsr = proxy_rates_from_window_features(features)
        if vsr == 0.0 and ssr == 0.0 and nsr == 0.0:
            rows.append(
                [
                    start.isoformat(),
                    end.isoformat(),
                    None,
                    None,
                    None,
                    STATUS_PENDING,
                    "Fase 2.2: VSR/SSR/NSR no disponible en catalogo actual.",
                ]
            )
            continue

        rows.append(
            [
                start.isoformat(),
                end.isoformat(),
                vsr,
                ssr,
                nsr,
                STATUS_PROXY,
                (
                    "Proxy InSAR desde catalogo sismico internacional "
                    f"(benioff={features.get('benioff_rate', 0.0):.3f}, "
                    f"delta_m={features.get('delta_m', 0.0):.3f})."
                ),
            ]
        )
    return rows


def parse_insar_gnss_rows(rows: Sequence[Sequence[Any]]) -> list[InsarGnssObservation]:
    observations: list[InsarGnssObservation] = []
    for row in rows:
        if len(row) < len(INSAR_GNSS_HEADERS):
            continue
        start = _parse_date(row[0])
        end = _parse_date(row[1])
        if start is None or end is None:
            continue
        observations.append(
            InsarGnssObservation(
                window_start=start,
                window_end=end,
                vsr_mm_per_year=_as_float(row[2]),
                ssr_mm_per_year=_as_float(row[3]),
                nsr_mm_per_year=_as_float(row[4]),
                data_status=str(row[5]) if row[5] is not None else STATUS_PENDING,
                notes=str(row[6]) if len(row) > 6 and row[6] is not None else "",
            )
        )
    return observations


def _window_overlap_days(
    a_start: date,
    a_end: date,
    b_start: date,
    b_end: date,
) -> int:
    overlap_start = max(a_start, b_start)
    overlap_end = min(a_end, b_end)
    if overlap_end < overlap_start:
        return 0
    return (overlap_end - overlap_start).days + 1


def select_insar_for_event_window(
    observations: Sequence[InsarGnssObservation],
    event_start: date,
    event_end: date,
) -> InsarGnssObservation | None:
    if not observations:
        return None

    ranked = sorted(
        observations,
        key=lambda obs: (
            _window_overlap_days(obs.window_start, obs.window_end, event_start, event_end),
            -abs((obs.window_end - event_start).days),
        ),
        reverse=True,
    )
    best = ranked[0]
    if _window_overlap_days(best.window_start, best.window_end, event_start, event_end) == 0:
        return min(
            observations,
            key=lambda obs: abs((obs.window_end - event_start).days),
        )
    return best


def resolve_insar_from_event_document(
    data: dict[str, Any],
    international_payload: dict[str, Any] | None,
) -> tuple[float | None, str, dict[str, Any]]:
    """Resuelve desplazamiento InSAR para un caso usando filas del workflow internacional."""
    if international_payload is None:
        return None, "unknown", {"connected": False}

    rows = international_payload.get("insar_gnss_rows")
    if not isinstance(rows, list):
        return None, "unknown", {"connected": False, "reason": "missing_insar_gnss_rows"}

    observations = parse_insar_gnss_rows(rows)
    event_start, event_end = _event_window_dates(data)
    if event_start is None or event_end is None:
        anomaly = international_payload.get("anomaly_reference_window")
        selected = _select_from_anomaly_reference(anomaly, observations)
    else:
        selected = select_insar_for_event_window(observations, event_start, event_end)

    if selected is None:
        return None, "unknown", {"connected": True, "reason": "no_matching_window"}

    displacement = selected.displacement_cm()
    metadata = {
        "connected": True,
        "source": "international_calculation_workflow",
        "window_start": selected.window_start.isoformat(),
        "window_end": selected.window_end.isoformat(),
        "vsr_mm_per_year": selected.vsr_mm_per_year,
        "ssr_mm_per_year": selected.ssr_mm_per_year,
        "nsr_mm_per_year": selected.nsr_mm_per_year,
        "data_status": selected.data_status,
        "displacement_cm": displacement,
        "notes": selected.notes,
    }
    return displacement, selected.insar_quality(), metadata


def build_geological_insar_bridge_summary(
    international_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = international_payload.get("insar_gnss_rows")
    observations = parse_insar_gnss_rows(rows) if isinstance(rows, list) else []
    latest = observations[-1] if observations else None
    return {
        "status": "connected",
        "model_target": "fcn_geoespacial_geologico",
        "rows_available": len(observations),
        "latest_window": (
            f"{latest.window_start.isoformat()}->{latest.window_end.isoformat()}"
            if latest
            else "-"
        ),
        "latest_displacement_cm": latest.displacement_cm() if latest else None,
        "latest_data_status": latest.data_status if latest else STATUS_PENDING,
    }


def load_international_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at root of {path}")
    return data


def find_latest_international_payload(root: Path) -> Path | None:
    files = sorted(root.glob("storage/venezuela/international/**/international_estimation_*.json"))
    return files[-1] if files else None


def _event_window_dates(data: dict[str, Any]) -> tuple[date | None, date | None]:
    time_window = data.get("time_window")
    if not isinstance(time_window, dict):
        return None, None
    start = _parse_date(time_window.get("start_date"))
    end = _parse_date(time_window.get("end_date"))
    return start, end


def _select_from_anomaly_reference(
    anomaly_reference_window: Any,
    observations: Sequence[InsarGnssObservation],
) -> InsarGnssObservation | None:
    if not isinstance(anomaly_reference_window, str) or "->" not in anomaly_reference_window:
        return observations[-1] if observations else None
    start_text, end_text = anomaly_reference_window.split("->", 1)
    start = _parse_date(start_text.strip())
    end = _parse_date(end_text.strip())
    if start is None or end is None:
        return observations[-1] if observations else None
    for obs in observations:
        if obs.window_start == start and obs.window_end == end:
            return obs
    return select_insar_for_event_window(observations, start, end)


def _parse_date(value: Any) -> date | None:
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


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
