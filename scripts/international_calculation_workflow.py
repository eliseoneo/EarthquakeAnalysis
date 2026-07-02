from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from layer_a.ingestion.ingv_client import download_ingv_catalog
from layer_a.ingestion.sgc_client import download_sgc_catalog
from layer_a.ingestion.usgs_client import download_usgs_catalog
from layer_a.paths import RAW_DIR
from geological_model.insar_bridge import (
    INSAR_GNSS_HEADERS,
    STATUS_MEASURED,
    STATUS_PROXY,
    build_geological_insar_bridge_summary,
    build_insar_gnss_rows,
)
from validation import ROOT

SOURCE_CONFIG: dict[str, dict[str, Any]] = {
    "usgs": {
        "country": "USA",
        "label": "USGS",
        "fallback": RAW_DIR / "catalog_usgs.json",
    },
    "ingv": {
        "country": "Italia",
        "label": "INGV",
        "fallback": RAW_DIR / "catalog_ingv.json",
    },
    "sgc": {
        "country": "Colombia",
        "label": "SGC",
        "fallback": RAW_DIR / "catalog_sgc.json",
    },
}

VENEZUELA_FOCUS_BBOX: dict[str, float] = {
    "min_lat": 0.3,
    "max_lat": 13.5,
    "min_lon": -73.7,
    "max_lon": -59.7,
}

ANOMALY_REFERENCE_DATE = date(2026, 6, 26)
ALTERNATIVE_THRESHOLD_MAGNITUDE = 4.5
WALK_FORWARD_MIN_TRAIN = 8
WALK_FORWARD_TEST_SIZE = 3
WALK_FORWARD_STEP = 3
PLATT_CALIBRATION_FRACTION = 0.2

FEATURE_ORDER = [
    "n_events",
    "m_mean",
    "gr_b",
    "gr_a",
    "benioff_rate",
    "delta_m",
    "mu_recurrence_days",
    "eta_rms",
    "n_usgs",
    "n_ingv",
    "n_sgc",
    "max_magnitude_in_window",
    "benioff_accel",
    "gr_b_delta",
    "event_rate_trend",
]

INSAR_GNSS_PLACEHOLDER_HEADERS = INSAR_GNSS_HEADERS

SIMILARITY_HEADERS = [
    "window_start",
    "window_end",
    "target_end",
    "similarity_to_anomaly",
]


@dataclass(frozen=True)
class SeismicSample:
    event_id: str
    source: str
    country: str
    dt_utc: datetime
    latitude: float
    longitude: float
    magnitude: float


@dataclass(frozen=True)
class WindowSample:
    start_date: date
    end_date: date
    target_end_date: date
    features: dict[str, float]
    target_probability_label: int
    target_probability_label_m45: int
    target_exceedance_prob: float
    target_mmax: float


def _as_utc_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min).replace(tzinfo=timezone.utc)
    end = datetime.combine(day, time.max).replace(tzinfo=timezone.utc)
    return start, end


def _parse_event_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _in_bbox(lat: float, lon: float, bbox: dict[str, float]) -> bool:
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def _event_from_row(row: dict[str, Any], source: str, country: str) -> SeismicSample | None:
    dt = _parse_event_datetime(row.get("datetime_utc"))
    lat = _safe_float(row.get("latitude"))
    lon = _safe_float(row.get("longitude"))
    mag = _safe_float(row.get("magnitude"))
    event_id_raw = row.get("event_id")
    if dt is None or lat is None or lon is None or mag is None:
        return None
    event_id = str(event_id_raw).strip() if isinstance(event_id_raw, str) else ""
    if not event_id:
        event_id = f"{source}_{int(dt.timestamp())}"
    return SeismicSample(
        event_id=event_id,
        source=source,
        country=country,
        dt_utc=dt,
        latitude=lat,
        longitude=lon,
        magnitude=mag,
    )


def _read_fallback_events(path: Path, source: str, country: str) -> list[SeismicSample]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("events", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []

    parsed: list[SeismicSample] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ev = _event_from_row(row, source=source, country=country)
        if ev is not None:
            parsed.append(ev)
    return parsed


def _download_live_events(
    source: str,
    start_date: date,
    end_date: date,
    min_magnitude: float,
    bbox: dict[str, float],
) -> tuple[list[dict[str, Any]], str]:
    if source == "usgs":
        rows, status = download_usgs_catalog(
            start_date=start_date,
            end_date=end_date,
            min_magnitude=min_magnitude,
            bbox=bbox,
        )
        return rows, status
    if source == "ingv":
        rows, status = download_ingv_catalog(
            start_date=start_date,
            end_date=end_date,
            min_magnitude=min_magnitude,
            bbox=bbox,
        )
        return rows, status
    if source == "sgc":
        rows, status = download_sgc_catalog(
            start_date=start_date,
            end_date=end_date,
            max_events=400,
        )
        return rows, status
    return [], "unsupported source"


def load_international_events(
    as_of_date: date,
    lookback_days: int,
    min_magnitude: float,
    use_live_sources: bool,
) -> tuple[list[SeismicSample], list[list[str | int]]]:
    start_date = as_of_date - timedelta(days=max(lookback_days, 1))
    _, end_dt = _as_utc_day_bounds(as_of_date)

    merged: list[SeismicSample] = []
    source_rows: list[list[str | int]] = []

    for source_key, cfg in SOURCE_CONFIG.items():
        country = str(cfg["country"])
        bbox = dict(VENEZUELA_FOCUS_BBOX)
        fallback_path = Path(cfg["fallback"])
        status = "fallback"
        raw_rows: list[dict[str, Any]] = []

        if use_live_sources:
            try:
                raw_rows, live_status = _download_live_events(
                    source_key,
                    start_date,
                    as_of_date,
                    min_magnitude,
                    bbox,
                )
                status = f"live: {live_status}"
            except Exception as exc:  # pragma: no cover - depende de red externa.
                status = f"fallback ({type(exc).__name__})"

        parsed: list[SeismicSample] = []
        if raw_rows:
            for row in raw_rows:
                if not isinstance(row, dict):
                    continue
                ev = _event_from_row(row, source=source_key, country=country)
                if ev is None:
                    continue
                if ev.magnitude < min_magnitude:
                    continue
                if not _in_bbox(ev.latitude, ev.longitude, bbox):
                    continue
                if not (start_date <= ev.dt_utc.date() <= as_of_date):
                    continue
                parsed.append(ev)

        if not parsed:
            fallback = _read_fallback_events(fallback_path, source=source_key, country=country)
            parsed = [
                ev
                for ev in fallback
                if ev.magnitude >= min_magnitude
                and _in_bbox(ev.latitude, ev.longitude, bbox)
                and start_date <= ev.dt_utc.date() <= as_of_date
            ]
            if status.startswith("live"):
                status = f"{status}; fallback used"

        parsed.sort(key=lambda ev: ev.dt_utc)
        merged.extend(parsed)

        first_dt = parsed[0].dt_utc.date().isoformat() if parsed else "-"
        last_dt = parsed[-1].dt_utc.date().isoformat() if parsed else "-"
        source_rows.append([str(cfg["label"]), country, f"{status}; focus=Venezuela", len(parsed), first_dt, last_dt])

    merged.sort(key=lambda ev: ev.dt_utc)

    dedup: dict[str, SeismicSample] = {}
    for ev in merged:
        dedup.setdefault(ev.event_id, ev)

    deduped = sorted(dedup.values(), key=lambda item: item.dt_utc)
    deduped = [ev for ev in deduped if ev.dt_utc <= end_dt]
    return deduped, source_rows


def _linear_regression(x: list[float], y: list[float]) -> tuple[float, float, float]:
    n = len(x)
    if n < 2:
        return 0.0, y[0] if y else 0.0, 0.0
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    ss_xx = sum((xi - x_mean) ** 2 for xi in x)
    if ss_xx <= 0:
        return 0.0, y_mean, 0.0
    ss_xy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    preds = [slope * xi + intercept for xi in x]
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    ss_res = sum((yi - pi) ** 2 for yi, pi in zip(y, preds))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return slope, intercept, r2


def _gr_parameters(magnitudes: list[float]) -> tuple[float, float, float]:
    if len(magnitudes) < 3:
        return 1.0, 0.0, 0.0

    m_min = min(magnitudes)
    m_max = max(magnitudes)
    if m_max - m_min < 0.2:
        return 1.0, 0.0, 0.0

    thresholds: list[float] = []
    cumulative_counts: list[float] = []
    step = 0.2
    current = m_min
    while current <= m_max + 1e-9:
        count = sum(1 for m in magnitudes if m >= current)
        if count >= 2:
            thresholds.append(current)
            cumulative_counts.append(float(count))
        current += step

    if len(thresholds) < 2:
        return 1.0, 0.0, 0.0

    y = [math.log10(val) for val in cumulative_counts]
    slope, intercept, _ = _linear_regression(thresholds, y)
    fitted = [slope * x + intercept for x in thresholds]
    eta = math.sqrt(sum((obs - fit) ** 2 for obs, fit in zip(y, fitted)) / len(y))

    b_value = max(0.4, min(1.8, -slope if slope != 0 else 1.0))
    a_value = intercept
    return b_value, a_value, eta


def _benioff_rate(magnitudes: list[float], window_days: int) -> float:
    if not magnitudes:
        return 0.0
    benioff_sum = sum(10 ** (0.75 * m + 2.4) for m in magnitudes)
    return benioff_sum / max(float(window_days), 1.0)


def _mu_recurrence_days(events: list[SeismicSample], fallback_days: int) -> float:
    if len(events) < 2:
        return float(fallback_days)
    gaps: list[float] = []
    for prev, current in zip(events, events[1:]):
        delta_days = (current.dt_utc - prev.dt_utc).total_seconds() / 86400.0
        if delta_days > 0:
            gaps.append(delta_days)
    if not gaps:
        return float(fallback_days)
    return sum(gaps) / len(gaps)


def _window_features(events: list[SeismicSample], window_days: int) -> dict[str, float]:
    magnitudes = [ev.magnitude for ev in events]
    n_events = float(len(events))
    m_mean = sum(magnitudes) / n_events if magnitudes else 0.0
    b_value, a_value, eta = _gr_parameters(magnitudes)
    benioff = _benioff_rate(magnitudes, window_days)
    expected_max = min(magnitudes) + (math.log10(max(n_events, 1.0)) / max(b_value, 0.1)) if magnitudes else 0.0
    observed_max = max(magnitudes) if magnitudes else 0.0
    delta_m = observed_max - expected_max
    mu = _mu_recurrence_days(events, fallback_days=window_days)

    by_source = {"usgs": 0.0, "ingv": 0.0, "sgc": 0.0}
    for ev in events:
        by_source[ev.source] = by_source.get(ev.source, 0.0) + 1.0

    return {
        "n_events": n_events,
        "m_mean": m_mean,
        "gr_b": b_value,
        "gr_a": a_value,
        "benioff_rate": benioff,
        "delta_m": delta_m,
        "mu_recurrence_days": mu,
        "eta_rms": eta,
        "n_usgs": by_source.get("usgs", 0.0),
        "n_ingv": by_source.get("ingv", 0.0),
        "n_sgc": by_source.get("sgc", 0.0),
        "max_magnitude_in_window": observed_max,
        "benioff_accel": 0.0,
        "gr_b_delta": 0.0,
        "event_rate_trend": 0.0,
    }


def _enrich_trend_features(
    features: dict[str, float],
    window_events: list[SeismicSample],
    window_days: int,
    prev_benioff: float | None,
) -> dict[str, float]:
    enriched = dict(features)
    if len(window_events) >= 4:
        mid = len(window_events) // 2
        first_half = window_events[:mid]
        second_half = window_events[mid:]
        b_first, _, _ = _gr_parameters([ev.magnitude for ev in first_half])
        b_second, _, _ = _gr_parameters([ev.magnitude for ev in second_half])
        enriched["gr_b_delta"] = round(b_second - b_first, 4)
        half_days = max(window_days / 2.0, 1.0)
        rate_first = len(first_half) / half_days
        rate_second = len(second_half) / half_days
        enriched["event_rate_trend"] = round(rate_second - rate_first, 4)
        ben_first = _benioff_rate([ev.magnitude for ev in first_half], int(half_days))
        ben_second = _benioff_rate([ev.magnitude for ev in second_half], int(half_days))
        enriched["benioff_accel"] = round(ben_second - ben_first, 4)
    if prev_benioff is not None:
        enriched["benioff_accel"] = round(enriched["benioff_rate"] - prev_benioff, 4)
    return enriched


def _gr_exceedance_probability(
    gr_a: float,
    gr_b: float,
    rate_per_day: float,
    horizon_days: int,
    threshold: float,
) -> float:
    if rate_per_day <= 0 or horizon_days <= 0:
        return 0.0
    lambda_eff = rate_per_day * horizon_days
    nu = 10 ** (gr_a - gr_b * threshold)
    mean_exceed = lambda_eff * max(nu, 1e-12)
    return max(0.0, min(1.0, 1.0 - math.exp(-mean_exceed)))


def _gr_tail_mmax_forecast(
    gr_a: float,
    gr_b: float,
    rate_per_day: float,
    horizon_days: int,
) -> float:
    lambda_eff = max(rate_per_day * horizon_days, 1.0)
    estimate = (gr_a + math.log10(lambda_eff)) / max(gr_b, 0.1)
    return max(0.0, min(9.5, estimate))


def _gr_tail_predictions(
    samples: list[WindowSample],
    horizon_days: int,
    window_days: int,
    exceedance_threshold: float = ALTERNATIVE_THRESHOLD_MAGNITUDE,
) -> tuple[list[float], list[float]]:
    exceedance: list[float] = []
    mmax: list[float] = []
    for sample in samples:
        feats = sample.features
        rate = float(feats.get("n_events", 0.0)) / max(float(window_days), 1.0)
        gr_a = float(feats.get("gr_a", 0.0))
        gr_b = float(feats.get("gr_b", 1.0))
        exceedance.append(
            _gr_exceedance_probability(
                gr_a,
                gr_b,
                rate,
                horizon_days,
                exceedance_threshold,
            )
        )
        mmax.append(_gr_tail_mmax_forecast(gr_a, gr_b, rate, horizon_days))
    return exceedance, mmax


def _calibrate_probabilities(
    raw_probs: list[float],
    cal_raw: list[float],
    cal_labels: list[int],
    *,
    use_platt: bool,
) -> list[float]:
    if not use_platt or not cal_raw:
        return raw_probs
    platt_scale, platt_shift = _fit_platt_scaling(cal_raw, cal_labels)
    return _apply_platt_scaling(raw_probs, platt_scale, platt_shift)


def build_window_dataset(
    events: list[SeismicSample],
    as_of_date: date,
    lookback_days: int,
    window_days: int,
    stride_days: int,
    horizon_days: int,
    threshold_magnitude: float,
    alternative_threshold_magnitude: float = ALTERNATIVE_THRESHOLD_MAGNITUDE,
) -> list[WindowSample]:
    if not events:
        return []

    start_limit = as_of_date - timedelta(days=max(lookback_days, 1))
    end_limit = as_of_date
    step = timedelta(days=max(stride_days, 1))
    window_delta = timedelta(days=max(window_days, 1))
    horizon_delta = timedelta(days=max(horizon_days, 1))

    cursor = start_limit
    samples: list[WindowSample] = []
    prev_benioff: float | None = None

    while cursor + window_delta + horizon_delta <= end_limit + timedelta(days=1):
        window_start = cursor
        window_end = cursor + window_delta
        target_end = window_end + horizon_delta

        window_events = [
            ev
            for ev in events
            if window_start <= ev.dt_utc.date() < window_end
        ]
        future_events = [
            ev
            for ev in events
            if window_end <= ev.dt_utc.date() < target_end
        ]

        if len(window_events) >= 3:
            base_features = _window_features(window_events, window_days=window_days)
            features = _enrich_trend_features(
                base_features,
                window_events,
                window_days=window_days,
                prev_benioff=prev_benioff,
            )
            prev_benioff = float(features["benioff_rate"])
            future_max = max((ev.magnitude for ev in future_events), default=0.0)
            rate_per_day = float(features["n_events"]) / max(float(window_days), 1.0)
            exceedance_prob = _gr_exceedance_probability(
                float(features["gr_a"]),
                float(features["gr_b"]),
                rate_per_day,
                horizon_days,
                threshold_magnitude,
            )
            label = 1 if future_max >= threshold_magnitude else 0
            label_m45 = 1 if future_max >= alternative_threshold_magnitude else 0
            samples.append(
                WindowSample(
                    start_date=window_start,
                    end_date=window_end - timedelta(days=1),
                    target_end_date=target_end - timedelta(days=1),
                    features=features,
                    target_probability_label=label,
                    target_probability_label_m45=label_m45,
                    target_exceedance_prob=exceedance_prob,
                    target_mmax=future_max,
                )
            )
        cursor += step

    return samples


def _feature_matrix(
    samples: list[WindowSample],
) -> tuple[
    list[list[float]],
    list[int],
    list[int],
    list[float],
    list[float],
    list[tuple[date, date, date]],
]:
    matrix: list[list[float]] = []
    labels: list[int] = []
    labels_m45: list[int] = []
    exceedance_targets: list[float] = []
    mmax_targets: list[float] = []
    spans: list[tuple[date, date, date]] = []
    for sample in samples:
        matrix.append([float(sample.features.get(name, 0.0)) for name in FEATURE_ORDER])
        labels.append(int(sample.target_probability_label))
        labels_m45.append(int(sample.target_probability_label_m45))
        exceedance_targets.append(float(sample.target_exceedance_prob))
        mmax_targets.append(float(sample.target_mmax))
        spans.append((sample.start_date, sample.end_date, sample.target_end_date))
    return matrix, labels, labels_m45, exceedance_targets, mmax_targets, spans


def _standardize(train_x: list[list[float]], test_x: list[list[float]]) -> tuple[list[list[float]], list[list[float]], list[float], list[float]]:
    if not train_x:
        return train_x, test_x, [], []
    feature_count = len(train_x[0])
    means: list[float] = []
    stds: list[float] = []

    for idx in range(feature_count):
        values = [row[idx] for row in train_x]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance) if variance > 0 else 1.0
        means.append(mean)
        stds.append(std)

    def _apply(rows: list[list[float]]) -> list[list[float]]:
        out: list[list[float]] = []
        for row in rows:
            out.append([(row[i] - means[i]) / stds[i] for i in range(feature_count)])
        return out

    return _apply(train_x), _apply(test_x), means, stds


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _train_logistic(
    x: list[list[float]],
    y: list[int],
    epochs: int = 500,
    lr: float = 0.08,
    class_weight: bool = True,
) -> tuple[list[float], float]:
    if not x:
        return [], 0.0
    feature_count = len(x[0])
    weights = [0.0 for _ in range(feature_count)]
    bias = 0.0
    n = float(len(x))
    positives = float(sum(y))
    negatives = n - positives
    pos_weight = (negatives / positives) if class_weight and positives > 0 else 1.0

    for _ in range(epochs):
        grad_w = [0.0 for _ in range(feature_count)]
        grad_b = 0.0
        for row, target in zip(x, y):
            linear = sum(w * val for w, val in zip(weights, row)) + bias
            pred = _sigmoid(linear)
            sample_weight = pos_weight if target == 1 else 1.0
            diff = (pred - float(target)) * sample_weight
            for j, val in enumerate(row):
                grad_w[j] += diff * val
            grad_b += diff
        for j in range(feature_count):
            weights[j] -= lr * (grad_w[j] / n)
        bias -= lr * (grad_b / n)

    return weights, bias


def _train_linear(x: list[list[float]], y: list[float], epochs: int = 700, lr: float = 0.02) -> tuple[list[float], float]:
    if not x:
        return [], 0.0
    feature_count = len(x[0])
    weights = [0.0 for _ in range(feature_count)]
    bias = 0.0
    n = float(len(x))

    for _ in range(epochs):
        grad_w = [0.0 for _ in range(feature_count)]
        grad_b = 0.0
        for row, target in zip(x, y):
            pred = sum(w * val for w, val in zip(weights, row)) + bias
            diff = pred - target
            for j, val in enumerate(row):
                grad_w[j] += diff * val
            grad_b += diff
        for j in range(feature_count):
            weights[j] -= lr * (grad_w[j] / n)
        bias -= lr * (grad_b / n)

    return weights, bias


def _predict_logistic(x: list[list[float]], weights: list[float], bias: float) -> list[float]:
    return [_sigmoid(sum(w * v for w, v in zip(weights, row)) + bias) for row in x]


def _predict_linear(x: list[list[float]], weights: list[float], bias: float) -> list[float]:
    return [sum(w * v for w, v in zip(weights, row)) + bias for row in x]


def _logit(probability: float) -> float:
    clipped = min(max(probability, 1e-6), 1 - 1e-6)
    return math.log(clipped / (1.0 - clipped))


def _fit_platt_scaling(
    raw_probs: list[float],
    labels: list[int],
    epochs: int = 250,
    lr: float = 0.1,
) -> tuple[float, float]:
    if not raw_probs:
        return 1.0, 0.0
    scale = 1.0
    shift = 0.0
    n = float(len(raw_probs))
    for _ in range(epochs):
        grad_scale = 0.0
        grad_shift = 0.0
        for prob, target in zip(raw_probs, labels):
            linear = scale * _logit(prob) + shift
            pred = _sigmoid(linear)
            diff = pred - float(target)
            logit_val = _logit(prob)
            grad_scale += diff * logit_val
            grad_shift += diff
        scale -= lr * (grad_scale / n)
        shift -= lr * (grad_shift / n)
    return scale, shift


def _apply_platt_scaling(raw_probs: list[float], scale: float, shift: float) -> list[float]:
    return [_sigmoid(scale * _logit(prob) + shift) for prob in raw_probs]


def _walk_forward_split_indices(
    sample_count: int,
    min_train: int,
    test_size: int,
    step: int,
) -> list[tuple[int, int]]:
    splits: list[tuple[int, int]] = []
    train_end = min_train
    while train_end + test_size <= sample_count:
        splits.append((train_end, train_end + test_size))
        train_end += step
    if not splits and sample_count >= min_train + 2:
        splits.append((min_train, sample_count))
    return splits


def _average_metric_dicts(metrics: list[dict[str, float]]) -> dict[str, float]:
    if not metrics:
        return {}
    keys = metrics[0].keys()
    return {key: sum(item[key] for item in metrics) / len(metrics) for key in keys}


def _classification_metrics(y_true: list[int], y_prob: list[float], threshold: float = 0.5) -> dict[str, float]:
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    gm = math.sqrt(max(recall * specificity, 0.0))

    ranked = sorted(zip(y_prob, y_true), key=lambda row: row[0], reverse=True)
    positives = max(sum(y_true), 1)
    tp_running = 0
    fp_running = 0
    pr_points: list[tuple[float, float]] = []
    for _, target in ranked:
        if target == 1:
            tp_running += 1
        else:
            fp_running += 1
        rec = tp_running / positives
        prec = tp_running / max(tp_running + fp_running, 1)
        pr_points.append((rec, prec))

    prc_auc = 0.0
    prev_rec = 0.0
    prev_prec = 1.0
    for rec, prec in pr_points:
        prc_auc += (rec - prev_rec) * ((prec + prev_prec) / 2.0)
        prev_rec = rec
        prev_prec = prec

    alarm_fraction = (tp + fp) / max(len(y_true), 1)
    missed_fraction = fn / max((tp + fn), 1)
    l_test = 0.0
    for yt, prob in zip(y_true, y_prob):
        clipped = min(max(prob, 1e-6), 1 - 1e-6)
        l_test += yt * math.log(clipped) + (1 - yt) * math.log(1 - clipped)
    l_test /= max(len(y_true), 1)

    return {
        "f1": f1,
        "gm": gm,
        "prc_auc": prc_auc,
        "molchan_alarm_fraction": alarm_fraction,
        "molchan_missed_fraction": missed_fraction,
        "l_test_log_likelihood": l_test,
    }


def _optimal_classification_threshold(y_true: list[int], y_prob: list[float]) -> float:
    best_threshold = 0.5
    best_f1 = -1.0
    for step in range(1, 100):
        threshold = step / 100.0
        metrics = _classification_metrics(y_true, y_prob, threshold=threshold)
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_threshold = threshold
    return best_threshold


def _walk_forward_classification_evaluation(
    matrix: list[list[float]],
    labels: list[int],
    min_train: int,
    test_size: int,
    step: int,
    *,
    use_platt: bool = True,
    platt_calibration_fraction: float = PLATT_CALIBRATION_FRACTION,
    class_weight: bool = True,
) -> tuple[dict[str, float], float, list[dict[str, float]]]:
    fold_metrics: list[dict[str, float]] = []
    thresholds: list[float] = []
    splits = _walk_forward_split_indices(len(matrix), min_train, test_size, step)
    for train_end, test_end in splits:
        train_x = matrix[:train_end]
        test_x = matrix[train_end:test_end]
        train_y = labels[:train_end]
        test_y = labels[train_end:test_end]
        if len(test_x) < 1:
            continue
        cal_size = max(1, int(len(train_x) * platt_calibration_fraction)) if use_platt else 0
        fit_x = train_x[:-cal_size] if cal_size and len(train_x) > cal_size + 2 else train_x
        fit_y = train_y[:-cal_size] if cal_size and len(train_y) > cal_size + 2 else train_y
        cal_x = train_x[-cal_size:] if cal_size else []
        cal_y = train_y[-cal_size:] if cal_size else []
        train_x_std, test_x_std, _, _ = _standardize(fit_x + cal_x, test_x)
        fit_x_std = train_x_std[: len(fit_x)]
        cal_x_std = train_x_std[len(fit_x) :]
        weights, bias = _train_logistic(fit_x_std, fit_y, class_weight=class_weight)
        test_raw = _predict_logistic(test_x_std, weights, bias)
        if use_platt and cal_x_std:
            cal_raw = _predict_logistic(cal_x_std, weights, bias)
            test_probs = _calibrate_probabilities(test_raw, cal_raw, cal_y, use_platt=True)
            thresholds.append(_optimal_classification_threshold(cal_y, cal_raw))
        else:
            test_probs = test_raw
            thresholds.append(_optimal_classification_threshold(train_y, test_raw))
        fold_metrics.append(_classification_metrics(test_y, test_probs))
    avg_threshold = sum(thresholds) / len(thresholds) if thresholds else 0.5
    return _average_metric_dicts(fold_metrics), avg_threshold, fold_metrics


def _regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    n = max(len(y_true), 1)
    mse = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred)) / n
    mae = sum(abs(yt - yp) for yt, yp in zip(y_true, y_pred)) / n
    y_mean = sum(y_true) / n if y_true else 0.0
    ss_tot = sum((yt - y_mean) ** 2 for yt in y_true)
    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    pairs = list(zip(y_true, y_pred))
    if len(pairs) >= 2:
        x = [pair[0] for pair in pairs]
        y = [pair[1] for pair in pairs]
        x_mean = sum(x) / len(x)
        y_mean_pred = sum(y) / len(y)
        cov = sum((xi - x_mean) * (yi - y_mean_pred) for xi, yi in zip(x, y))
        x_var = sum((xi - x_mean) ** 2 for xi in x)
        y_var = sum((yi - y_mean_pred) ** 2 for yi in y)
        s_test = cov / math.sqrt(x_var * y_var) if x_var > 0 and y_var > 0 else 0.0
    else:
        s_test = 0.0

    return {
        "mse": mse,
        "mae": mae,
        "r2": r2,
        "s_test_spatial_skill": s_test,
    }


def _feature_importance(
    feature_names: list[str],
    w_cls: list[float],
    w_reg: list[float],
) -> list[list[float | str]]:
    score_pairs: list[tuple[str, float]] = []
    for name, cls_w, reg_w in zip(feature_names, w_cls, w_reg):
        score = abs(cls_w) + abs(reg_w)
        score_pairs.append((name, score))

    total = sum(score for _, score in score_pairs) or 1.0
    rows = [[name, score, (score / total) * 100.0] for name, score in score_pairs]
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def _ablation_importance(
    x_test: list[list[float]],
    y_cls: list[int],
    y_reg: list[float],
    w_cls: list[float],
    b_cls: float,
    w_reg: list[float],
    b_reg: float,
) -> list[float]:
    base_cls = _classification_metrics(y_cls, _predict_logistic(x_test, w_cls, b_cls))
    base_reg = _regression_metrics(y_reg, _predict_linear(x_test, w_reg, b_reg))
    base_score = 0.5 * base_cls["f1"] + 0.5 * max(0.0, base_reg["r2"])

    impacts: list[float] = []
    for idx in range(len(w_cls)):
        modified = [list(row) for row in x_test]
        for row in modified:
            row[idx] = 0.0
        cls_metric = _classification_metrics(y_cls, _predict_logistic(modified, w_cls, b_cls))
        reg_metric = _regression_metrics(y_reg, _predict_linear(modified, w_reg, b_reg))
        score = 0.5 * cls_metric["f1"] + 0.5 * max(0.0, reg_metric["r2"])
        impacts.append(max(0.0, base_score - score))
    return impacts


def _save_run(payload: dict[str, Any], as_of_date: date) -> Path:
    today = as_of_date
    out_dir = (
        ROOT
        / "storage"
        / "venezuela"
        / "international"
        / f"{today.year:04d}"
        / f"{today.month:02d}"
        / f"{today.day:02d}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"international_estimation_{stamp}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path


def _display_storage_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _scale_vector(row: list[float], means: list[float], stds: list[float]) -> list[float]:
    return [
        (row[i] - means[i]) / stds[i] if i < len(means) and i < len(stds) and stds[i] != 0 else row[i]
        for i in range(len(row))
    ]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def _select_anomaly_window(dataset: list[WindowSample], anomaly_date: date) -> WindowSample | None:
    if not dataset:
        return None
    for sample in dataset:
        if sample.start_date <= anomaly_date <= sample.end_date:
            return sample
    return min(dataset, key=lambda sample: abs((sample.end_date - anomaly_date).days))


def run_international_estimation(
    as_of_date: date,
    lookback_days: int,
    window_days: int,
    stride_days: int,
    horizon_days: int,
    threshold_magnitude: float,
    min_magnitude: float,
    use_live_sources: bool,
    use_live_insar_gnss: bool = False,
    alternative_threshold_magnitude: float = ALTERNATIVE_THRESHOLD_MAGNITUDE,
    walk_forward_min_train: int = WALK_FORWARD_MIN_TRAIN,
    walk_forward_test_size: int = WALK_FORWARD_TEST_SIZE,
    walk_forward_step: int = WALK_FORWARD_STEP,
    use_platt_calibration: bool = True,
    platt_calibration_fraction: float = PLATT_CALIBRATION_FRACTION,
    use_class_weight: bool = True,
) -> dict[str, Any]:
    events, source_table = load_international_events(
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        min_magnitude=min_magnitude,
        use_live_sources=use_live_sources,
    )
    dataset = build_window_dataset(
        events,
        as_of_date=as_of_date,
        lookback_days=lookback_days,
        window_days=window_days,
        stride_days=stride_days,
        horizon_days=horizon_days,
        threshold_magnitude=threshold_magnitude,
        alternative_threshold_magnitude=alternative_threshold_magnitude,
    )

    if len(dataset) < 6:
        return {
            "status": "insufficient_data",
            "message": "No hay suficientes ventanas para entrenar el modelo internacional.",
            "source_table": source_table,
            "feature_rows": [],
            "insar_gnss_rows": [],
            "similarity_rows": [],
            "anomaly_reference_window": "-",
            "prediction_rows": [],
            "metrics_rows": [],
            "importance_rows": [],
            "ablation_rows": [],
            "probability_plot": {"x": [], "y_prob": [], "y_true": []},
            "mmax_plot": {"x": [], "y_pred": [], "y_true": []},
            "storage_path": "-",
        }

    matrix, labels, labels_m45, exceedance_targets, mmax_targets, spans = _feature_matrix(dataset)
    wf_cls_metrics, operational_threshold, walk_forward_folds = _walk_forward_classification_evaluation(
        matrix,
        labels,
        min_train=walk_forward_min_train,
        test_size=walk_forward_test_size,
        step=walk_forward_step,
        use_platt=use_platt_calibration,
        platt_calibration_fraction=platt_calibration_fraction,
        class_weight=use_class_weight,
    )
    wf_cls_m45_metrics, operational_threshold_m45, _ = _walk_forward_classification_evaluation(
        matrix,
        labels_m45,
        min_train=walk_forward_min_train,
        test_size=walk_forward_test_size,
        step=walk_forward_step,
        use_platt=use_platt_calibration,
        platt_calibration_fraction=platt_calibration_fraction,
        class_weight=use_class_weight,
    )

    split_idx = max(walk_forward_min_train, len(dataset) - walk_forward_test_size)
    split_idx = min(split_idx, len(dataset) - 2)

    train_x = matrix[:split_idx]
    test_x = matrix[split_idx:]
    train_y_cls = labels[:split_idx]
    test_y_cls = labels[split_idx:]
    train_y_m45 = labels_m45[:split_idx]
    test_y_m45 = labels_m45[split_idx:]
    train_y_exceed = exceedance_targets[:split_idx]
    test_y_exceed = exceedance_targets[split_idx:]
    train_y_reg = mmax_targets[:split_idx]
    test_y_reg = mmax_targets[split_idx:]
    test_spans = spans[split_idx:]
    test_samples = dataset[split_idx:]

    cal_size = max(1, int(len(train_x) * platt_calibration_fraction)) if use_platt_calibration else 0
    fit_x = train_x[:-cal_size] if cal_size and len(train_x) > cal_size + 2 else train_x
    fit_y_cls = train_y_cls[:-cal_size] if cal_size and len(train_y_cls) > cal_size + 2 else train_y_cls
    fit_y_m45 = train_y_m45[:-cal_size] if cal_size and len(train_y_m45) > cal_size + 2 else train_y_m45
    cal_x = train_x[-cal_size:] if cal_size else []
    cal_y_cls = train_y_cls[-cal_size:] if cal_size else []
    cal_y_m45 = train_y_m45[-cal_size:] if cal_size else []

    train_x_std, test_x_std, means, stds = _standardize(fit_x + cal_x, test_x)
    fit_x_std = train_x_std[: len(fit_x)]
    cal_x_std = train_x_std[len(fit_x) :]

    w_cls, b_cls = _train_logistic(fit_x_std, fit_y_cls, class_weight=use_class_weight)
    w_cls_m45, b_cls_m45 = _train_logistic(fit_x_std, fit_y_m45, class_weight=use_class_weight)
    w_reg = [0.0 for _ in FEATURE_ORDER]
    b_reg = 0.0

    test_raw = _predict_logistic(test_x_std, w_cls, b_cls)
    test_raw_m45 = _predict_logistic(test_x_std, w_cls_m45, b_cls_m45)
    if use_platt_calibration and cal_x_std:
        cal_raw = _predict_logistic(cal_x_std, w_cls, b_cls)
        cal_raw_m45 = _predict_logistic(cal_x_std, w_cls_m45, b_cls_m45)
        cls_prob = _calibrate_probabilities(test_raw, cal_raw, cal_y_cls, use_platt=True)
        cls_prob_m45 = _calibrate_probabilities(test_raw_m45, cal_raw_m45, cal_y_m45, use_platt=True)
    else:
        cls_prob = test_raw
        cls_prob_m45 = test_raw_m45
    gr_exceed_pred, gr_mmax_pred = _gr_tail_predictions(
        test_samples,
        horizon_days,
        window_days,
        exceedance_threshold=alternative_threshold_magnitude,
    )

    cls_metrics = _classification_metrics(test_y_cls, cls_prob, threshold=operational_threshold)
    cls_m45_metrics = _classification_metrics(
        test_y_m45,
        cls_prob_m45,
        threshold=operational_threshold_m45,
    )
    reg_metrics = _regression_metrics(test_y_reg, gr_mmax_pred)
    exceedance_metrics = _regression_metrics(test_y_exceed, gr_exceed_pred)

    importance = _feature_importance(FEATURE_ORDER, w_cls, w_reg)
    ablation = _ablation_importance(test_x_std, test_y_cls, test_y_reg, w_cls, b_cls, w_reg, b_reg)
    ablation_rows = [
        [feature, impact]
        for feature, impact in sorted(zip(FEATURE_ORDER, ablation), key=lambda item: item[1], reverse=True)
    ]

    prediction_rows: list[list[str | float | int]] = []
    for span, y_true_prob, y_prob, y_true_m45, y_prob_m45, y_true_exceed, y_exceed, y_true_mmax, y_mmax in zip(
        test_spans,
        test_y_cls,
        cls_prob,
        test_y_m45,
        cls_prob_m45,
        test_y_exceed,
        gr_exceed_pred,
        test_y_reg,
        gr_mmax_pred,
    ):
        prediction_rows.append(
            [
                span[0].isoformat(),
                span[1].isoformat(),
                span[2].isoformat(),
                int(y_true_prob),
                float(y_prob),
                int(y_true_m45),
                float(y_prob_m45),
                float(y_true_exceed),
                float(y_exceed),
                float(y_true_mmax),
                float(y_mmax),
            ]
        )

    feature_rows: list[list[str | float]] = []
    for sample in dataset[-12:]:
        row: list[str | float] = [sample.start_date.isoformat(), sample.end_date.isoformat()]
        row.extend(float(sample.features.get(name, 0.0)) for name in FEATURE_ORDER)
        feature_rows.append(row)

    insar_gnss_rows = build_insar_gnss_rows(
        dataset,
        use_measured=use_live_insar_gnss,
        use_live=use_live_insar_gnss,
    )
    insar_fetch_meta = insar_gnss_rows and {
        "enabled": use_live_insar_gnss,
        "measured_rows": sum(
            1 for row in insar_gnss_rows if len(row) > 5 and row[5] == STATUS_MEASURED
        ),
        "proxy_rows": sum(
            1 for row in insar_gnss_rows if len(row) > 5 and row[5] != STATUS_MEASURED
        ),
    }

    anomaly_sample = _select_anomaly_window(dataset, ANOMALY_REFERENCE_DATE)
    anomaly_reference_window = "-"
    anomaly_scaled: list[float] = []
    if anomaly_sample is not None:
        anomaly_reference_window = (
            f"{anomaly_sample.start_date.isoformat()}->{anomaly_sample.end_date.isoformat()}"
        )
        anomaly_raw = [float(anomaly_sample.features.get(name, 0.0)) for name in FEATURE_ORDER]
        anomaly_scaled = _scale_vector(anomaly_raw, means, stds)

    similarity_rows: list[list[str | float]] = []
    for span, row_std in zip(test_spans, test_x_std):
        sim = _cosine_similarity(row_std, anomaly_scaled) if anomaly_scaled else 0.0
        similarity_rows.append(
            [
                span[0].isoformat(),
                span[1].isoformat(),
                span[2].isoformat(),
                float(sim),
            ]
        )

    metrics_rows = [
        ["F1", cls_metrics["f1"]],
        ["GM", cls_metrics["gm"]],
        ["PRC AUC", cls_metrics["prc_auc"]],
        ["Molchan alarm fraction", cls_metrics["molchan_alarm_fraction"]],
        ["Molchan missed fraction", cls_metrics["molchan_missed_fraction"]],
        ["L-test log-likelihood", cls_metrics["l_test_log_likelihood"]],
        ["F1 walk-forward avg", wf_cls_metrics.get("f1", 0.0)],
        ["PRC AUC walk-forward avg", wf_cls_metrics.get("prc_auc", 0.0)],
        ["F1 M>=4.5 holdout", cls_m45_metrics["f1"]],
        ["Operational threshold M>=5", operational_threshold],
        ["Operational threshold M>=4.5", operational_threshold_m45],
        ["MSE exceedance GR", exceedance_metrics["mse"]],
        ["MSE Mmax GR-tail", reg_metrics["mse"]],
        ["MAE Mmax GR-tail", reg_metrics["mae"]],
        ["R2 Mmax GR-tail", reg_metrics["r2"]],
        ["S-test spatial skill", reg_metrics["s_test_spatial_skill"]],
    ]

    payload = {
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of_date": as_of_date.isoformat(),
        "parameters": {
            "lookback_days": lookback_days,
            "window_days": window_days,
            "stride_days": stride_days,
            "horizon_days": horizon_days,
            "threshold_magnitude": threshold_magnitude,
            "alternative_threshold_magnitude": alternative_threshold_magnitude,
            "min_magnitude": min_magnitude,
            "use_live_sources": use_live_sources,
            "use_live_insar_gnss": use_live_insar_gnss,
            "validation_strategy": "walk_forward",
            "walk_forward_min_train": walk_forward_min_train,
            "walk_forward_test_size": walk_forward_test_size,
            "walk_forward_step": walk_forward_step,
            "class_weight": use_class_weight,
            "probability_calibration": "platt" if use_platt_calibration else "none",
            "platt_calibration_fraction": platt_calibration_fraction,
            "mmax_model": "gutenberg_richter_tail",
        },
        "event_count": len(events),
        "window_count": len(dataset),
        "training_windows": split_idx,
        "testing_windows": len(dataset) - split_idx,
        "walk_forward_folds": len(walk_forward_folds),
        "walk_forward_metrics": {
            "classification_m5": wf_cls_metrics,
            "classification_m45": wf_cls_m45_metrics,
            "operational_threshold_m5": operational_threshold,
            "operational_threshold_m45": operational_threshold_m45,
        },
        "source_table": source_table,
        "metrics_rows": metrics_rows,
        "importance_rows": importance,
        "ablation_rows": ablation_rows,
        "insar_gnss_rows": insar_gnss_rows,
        "insar_fetch_meta": insar_fetch_meta,
        "similarity_rows": similarity_rows,
        "anomaly_reference_window": anomaly_reference_window,
        "insar_gnss_placeholder_policy": {
            "fields": ["vsr_mm_per_year", "ssr_mm_per_year", "nsr_mm_per_year"],
            "status": STATUS_PROXY,
            "notes": (
                "Proxy conectado al FCN geologico via geological_model.insar_bridge; "
                "usar --use-live-insar-gnss o scripts/fetch_insar_gnss.py para datos MIDAS medidos."
            ),
        },
        "geological_insar_bridge": build_geological_insar_bridge_summary(
            {"insar_gnss_rows": insar_gnss_rows}
        ),
    }
    out_path = _save_run(payload, as_of_date=as_of_date)

    return {
        "status": "ok",
        "message": "Modelo internacional ejecutado correctamente.",
        "parameters": payload["parameters"],
        "window_count": len(dataset),
        "training_windows": split_idx,
        "testing_windows": len(dataset) - split_idx,
        "walk_forward_folds": len(walk_forward_folds),
        "source_table": source_table,
        "feature_rows": feature_rows,
        "insar_gnss_rows": insar_gnss_rows,
        "insar_fetch_meta": insar_fetch_meta,
        "similarity_rows": similarity_rows,
        "anomaly_reference_window": anomaly_reference_window,
        "geological_insar_bridge": payload["geological_insar_bridge"],
        "prediction_rows": prediction_rows,
        "metrics_rows": metrics_rows,
        "importance_rows": importance,
        "ablation_rows": ablation_rows,
        "walk_forward_metrics": {
            "classification_m5": wf_cls_metrics,
            "classification_m45": wf_cls_m45_metrics,
            "folds": walk_forward_folds,
        },
        "probability_plot": {
            "x": [f"{row[0]}->{row[2]}" for row in prediction_rows],
            "y_prob": [float(row[4]) for row in prediction_rows],
            "y_true": [float(row[3]) for row in prediction_rows],
        },
        "mmax_plot": {
            "x": [f"{row[0]}->{row[2]}" for row in prediction_rows],
            "y_pred": [float(row[10]) for row in prediction_rows],
            "y_true": [float(row[9]) for row in prediction_rows],
        },
        "storage_path": _display_storage_path(out_path),
    }


def _plot_probability_curve(payload: dict[str, Any]):
    import matplotlib.pyplot as plt

    data = payload.get("probability_plot", {})
    labels = data.get("x", [])
    pred = data.get("y_prob", [])
    truth = data.get("y_true", [])

    fig, ax = plt.subplots(figsize=(10, 4.6))
    if not labels:
        ax.text(0.5, 0.5, "Sin datos de proyeccion", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    x = list(range(len(labels)))
    ax.plot(x, [p * 100.0 for p in pred], marker="o", color="#2A9D8F", label="P(M>=umbral) pred")
    ax.plot(x, [v * 100.0 for v in truth], marker="x", linestyle="--", color="#E76F51", label="Evento real")
    ax.set_title("Fase 3-6: Clasificacion binaria por ventana")
    ax.set_ylabel("Probabilidad / Etiqueta (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(0, 105)
    ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


def _plot_mmax_curve(payload: dict[str, Any]):
    import matplotlib.pyplot as plt

    data = payload.get("mmax_plot", {})
    labels = data.get("x", [])
    pred = data.get("y_pred", [])
    truth = data.get("y_true", [])

    fig, ax = plt.subplots(figsize=(10, 4.6))
    if not labels:
        ax.text(0.5, 0.5, "Sin datos de regresion", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    x = list(range(len(labels)))
    ax.plot(x, pred, marker="o", color="#264653", label="Mmax pred")
    ax.plot(x, truth, marker="x", linestyle="--", color="#F4A261", label="Mmax real")
    ax.set_title("Fase 3-6: Regresion de magnitud maxima esperada")
    ax.set_ylabel("Magnitud Mw")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.legend(loc="upper left")
    fig.tight_layout()
    return fig


def _plot_importance(payload: dict[str, Any]):
    import matplotlib.pyplot as plt

    rows = payload.get("importance_rows", [])
    top = rows[:8]

    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    if not top:
        ax.text(0.5, 0.5, "Sin importancia disponible", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        return fig

    labels = [str(row[0]) for row in reversed(top)]
    values = [float(row[2]) for row in reversed(top)]
    ax.barh(labels, values, color="#457B9D")
    ax.set_title("Fase 8: Importancia relativa de variables")
    ax.set_xlabel("Importancia (%)")
    fig.tight_layout()
    return fig


def mount_international_calculation_panel(gr_module: Any, default_as_of: str) -> None:
    gr = gr_module

    gr.Markdown(
        "## Modelo Internacional de Calculo y Estimacion\n"
        "Fuentes: **Italia (INGV)**, **Colombia (SGC)** y **USA (USGS)**.\n"
        "Estructura metodologica: Fases 1-8 del documento de calculo.\n"
        "Foco geografico: **Venezuela**. Evento anomalo de referencia: **2026-06-26**."
    )
    gr.Markdown(
        "### Fase 1: Ventanas espacio-temporales\n"
        "Configura lookback, ventana, stride y horizonte para evaluacion pseudo-prospectiva."
    )

    with gr.Row():
        as_of = gr.Textbox(value=default_as_of, label="Fecha de corte (YYYY-MM-DD)")
        lookback_days = gr.Slider(120, 3650, value=900, step=10, label="Lookback (dias)")
        window_days = gr.Slider(14, 365, value=90, step=1, label="Ventana (dias)")
        stride_days = gr.Slider(1, 90, value=15, step=1, label="Stride (dias)")
        horizon_days = gr.Slider(7, 180, value=30, step=1, label="Horizonte target (dias)")

    with gr.Row():
        threshold_magnitude = gr.Number(value=5.0, label="Umbral clasificacion M >=", minimum=3.5, maximum=8.5)
        alternative_threshold = gr.Number(
            value=ALTERNATIVE_THRESHOLD_MAGNITUDE,
            label="Umbral alternativo M >=",
            minimum=3.5,
            maximum=7.0,
        )
        min_magnitude = gr.Number(value=3.0, label="Magnitud minima catalogo", minimum=1.0, maximum=7.0)
        use_live = gr.Checkbox(value=True, label="Usar APIs live (fallback local si falla)")

    gr.Markdown(
        "### Fase 1.1: Validacion walk-forward, calibracion Platt e InSAR MIDAS\n"
        "Ajusta la validacion temporal, la calibracion de probabilidades y la fuente InSAR/GNSS."
    )
    with gr.Row():
        wf_min_train = gr.Slider(4, 30, value=WALK_FORWARD_MIN_TRAIN, step=1, label="Walk-forward min train")
        wf_test_size = gr.Slider(1, 12, value=WALK_FORWARD_TEST_SIZE, step=1, label="Walk-forward test size")
        wf_step = gr.Slider(1, 15, value=WALK_FORWARD_STEP, step=1, label="Walk-forward step")
    with gr.Row():
        use_platt = gr.Checkbox(value=True, label="Calibracion Platt")
        platt_fraction = gr.Slider(
            0.05,
            0.5,
            value=PLATT_CALIBRATION_FRACTION,
            step=0.05,
            label="Fraccion calibracion Platt",
        )
        use_class_weight = gr.Checkbox(value=True, label="Class weight (balanceo de clases)")
        use_live_insar = gr.Checkbox(value=False, label="InSAR/GNSS MIDAS medido (NGL)")

    run_btn = gr.Button("Ejecutar calculo y estimacion internacional", variant="primary")

    gr.Markdown("### Fase 2: Feature engineering del catalogo sismico")
    source_table = gr.Dataframe(
        headers=["fuente", "pais", "estado", "eventos", "inicio", "fin"],
        datatype=["str", "str", "str", "number", "str", "str"],
        label="Resumen por fuente",
        interactive=False,
    )
    feature_table = gr.Dataframe(
        headers=["window_start", "window_end"] + FEATURE_ORDER,
        datatype=["str", "str"] + ["number" for _ in FEATURE_ORDER],
        label="Variables por ventana (ultimas 12)",
        interactive=False,
    )
    gr.Markdown("### Fase 2.2: InSAR/GNSS (proxy o MIDAS medido)")
    insar_gnss_table = gr.Dataframe(
        headers=INSAR_GNSS_PLACEHOLDER_HEADERS,
        datatype=["str", "str", "number", "number", "number", "str", "str"],
        label="VSR/SSR/NSR por ventana",
        interactive=False,
    )

    gr.Markdown("### Fases 3-5: Target dual + modelo de clasificacion y regresion")
    prediction_table = gr.Dataframe(
        headers=[
            "window_start",
            "window_end",
            "target_end",
            "target_cls_m5",
            "pred_prob_m5",
            "target_cls_m45",
            "pred_prob_m45",
            "target_exceedance",
            "pred_exceedance_gr",
            "target_mmax",
            "pred_mmax_gr",
        ],
        datatype=["str", "str", "str", "number", "number", "number", "number", "number", "number", "number", "number"],
        label="Predicciones en ventanas de prueba",
        interactive=False,
    )

    with gr.Row():
        prob_plot = gr.Plot(label="Clasificacion P(M>=umbral)")
        mmax_plot = gr.Plot(label="Regresion Mmax")

    gr.Markdown("### Fase 6-7: Metricas y validacion pseudo-prospectiva")
    metrics_table = gr.Dataframe(
        headers=["metrica", "valor"],
        datatype=["str", "number"],
        label="Metricas de evaluacion",
        interactive=False,
    )
    similarity_table = gr.Dataframe(
        headers=SIMILARITY_HEADERS,
        datatype=["str", "str", "str", "number"],
        label="Similitud con ventana anomala (2026-06-26)",
        interactive=False,
    )

    gr.Markdown("### Fase 8: Importancia de variables y ablacion")
    with gr.Row():
        importance_plot = gr.Plot(label="Importancia relativa top variables")
        importance_table = gr.Dataframe(
            headers=["feature", "score", "importance_percent"],
            datatype=["str", "number", "number"],
            label="Importancia por coeficientes",
            interactive=False,
        )

    ablation_table = gr.Dataframe(
        headers=["feature", "performance_drop"],
        datatype=["str", "number"],
        label="Ablacion (caida de performance)",
        interactive=False,
    )

    status_md = gr.Markdown()
    model_md = gr.Markdown()

    def _run(
        as_of_text: str,
        lookback_value: int,
        window_value: int,
        stride_value: int,
        horizon_value: int,
        threshold_value: float,
        alternative_threshold_value: float,
        min_mag_value: float,
        use_live_value: bool,
        wf_min_train_value: int,
        wf_test_size_value: int,
        wf_step_value: int,
        use_platt_value: bool,
        platt_fraction_value: float,
        use_class_weight_value: bool,
        use_live_insar_value: bool,
    ):
        try:
            as_of_date = datetime.strptime(str(as_of_text).strip(), "%Y-%m-%d").date()
        except ValueError:
            as_of_date = date.today()

        payload = run_international_estimation(
            as_of_date=as_of_date,
            lookback_days=int(lookback_value),
            window_days=int(window_value),
            stride_days=int(stride_value),
            horizon_days=int(horizon_value),
            threshold_magnitude=float(threshold_value),
            alternative_threshold_magnitude=float(alternative_threshold_value),
            min_magnitude=float(min_mag_value),
            use_live_sources=bool(use_live_value),
            use_live_insar_gnss=bool(use_live_insar_value),
            walk_forward_min_train=int(wf_min_train_value),
            walk_forward_test_size=int(wf_test_size_value),
            walk_forward_step=int(wf_step_value),
            use_platt_calibration=bool(use_platt_value),
            platt_calibration_fraction=float(platt_fraction_value),
            use_class_weight=bool(use_class_weight_value),
        )

        if payload.get("status") != "ok":
            status_text = (
                "### Estado\n"
                f"{payload.get('message', 'No fue posible ejecutar el modelo.')}\n\n"
                "Recomendacion: ampliar lookback o bajar magnitud minima."
            )
            model_text = "### Modelo\nSin entrenamiento por falta de muestras."
            return (
                status_text,
                model_text,
                payload.get("source_table", []),
                payload.get("feature_rows", []),
                payload.get("insar_gnss_rows", []),
                payload.get("prediction_rows", []),
                _plot_probability_curve(payload),
                _plot_mmax_curve(payload),
                payload.get("metrics_rows", []),
                payload.get("similarity_rows", []),
                _plot_importance(payload),
                payload.get("importance_rows", []),
                payload.get("ablation_rows", []),
            )

        params = payload.get("parameters", {})
        status_text = (
            "### Estado\n"
            f"{payload.get('message', 'Ejecucion completada.')}\n\n"
            f"- Ventanas: {payload.get('window_count', 0)}\n"
            f"- Entrenamiento: {payload.get('training_windows', 0)}\n"
            f"- Prueba: {payload.get('testing_windows', 0)}\n"
            f"- Walk-forward folds: {payload.get('walk_forward_folds', 0)}\n"
            f"- Ventana anomala: {payload.get('anomaly_reference_window', '-')}\n"
            f"- InSAR MIDAS: {'activo' if params.get('use_live_insar_gnss') else 'proxy'}\n"
            f"- Salida: {payload.get('storage_path', '-') }"
        )

        model_text = (
            "### Modelo (Fase 4)\n"
            f"- Umbral principal: M>={params.get('threshold_magnitude', threshold_value)}\n"
            f"- Umbral alternativo: M>={params.get('alternative_threshold_magnitude', alternative_threshold_value)}\n"
            f"- Walk-forward: train>={params.get('walk_forward_min_train')}, "
            f"test={params.get('walk_forward_test_size')}, step={params.get('walk_forward_step')}\n"
            f"- Calibracion: {params.get('probability_calibration', 'platt')} "
            f"(fraccion={params.get('platt_calibration_fraction', platt_fraction_value)})\n"
            f"- Class weight: {params.get('class_weight', use_class_weight_value)}\n"
            "- Regresion Mmax: cola Gutenberg-Richter.\n"
            "- Features: max_mag ventana, aceleracion Benioff, delta b-value, tendencia de tasa."
        )

        return (
            status_text,
            model_text,
            payload.get("source_table", []),
            payload.get("feature_rows", []),
            payload.get("insar_gnss_rows", []),
            payload.get("prediction_rows", []),
            _plot_probability_curve(payload),
            _plot_mmax_curve(payload),
            payload.get("metrics_rows", []),
            payload.get("similarity_rows", []),
            _plot_importance(payload),
            payload.get("importance_rows", []),
            payload.get("ablation_rows", []),
        )

    run_btn.click(
        fn=_run,
        inputs=[
            as_of,
            lookback_days,
            window_days,
            stride_days,
            horizon_days,
            threshold_magnitude,
            alternative_threshold,
            min_magnitude,
            use_live,
            wf_min_train,
            wf_test_size,
            wf_step,
            use_platt,
            platt_fraction,
            use_class_weight,
            use_live_insar,
        ],
        outputs=[
            status_md,
            model_md,
            source_table,
            feature_table,
            insar_gnss_table,
            prediction_table,
            prob_plot,
            mmax_plot,
            metrics_table,
            similarity_table,
            importance_plot,
            importance_table,
            ablation_table,
        ],
    )
