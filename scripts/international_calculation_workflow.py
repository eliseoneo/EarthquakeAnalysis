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
]

INSAR_GNSS_PLACEHOLDER_HEADERS = [
    "window_start",
    "window_end",
    "vsr_mm_per_year",
    "ssr_mm_per_year",
    "nsr_mm_per_year",
    "data_status",
    "notes",
]

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
    }


def build_window_dataset(
    events: list[SeismicSample],
    as_of_date: date,
    lookback_days: int,
    window_days: int,
    stride_days: int,
    horizon_days: int,
    threshold_magnitude: float,
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
            features = _window_features(window_events, window_days=window_days)
            future_max = max((ev.magnitude for ev in future_events), default=0.0)
            label = 1 if future_max >= threshold_magnitude else 0
            samples.append(
                WindowSample(
                    start_date=window_start,
                    end_date=window_end - timedelta(days=1),
                    target_end_date=target_end - timedelta(days=1),
                    features=features,
                    target_probability_label=label,
                    target_mmax=future_max,
                )
            )
        cursor += step

    return samples


def _feature_matrix(samples: list[WindowSample]) -> tuple[list[list[float]], list[int], list[float], list[tuple[date, date, date]]]:
    matrix: list[list[float]] = []
    labels: list[int] = []
    mmax_targets: list[float] = []
    spans: list[tuple[date, date, date]] = []
    for sample in samples:
        matrix.append([float(sample.features.get(name, 0.0)) for name in FEATURE_ORDER])
        labels.append(int(sample.target_probability_label))
        mmax_targets.append(float(sample.target_mmax))
        spans.append((sample.start_date, sample.end_date, sample.target_end_date))
    return matrix, labels, mmax_targets, spans


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


def _train_logistic(x: list[list[float]], y: list[int], epochs: int = 500, lr: float = 0.08) -> tuple[list[float], float]:
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
            linear = sum(w * val for w, val in zip(weights, row)) + bias
            pred = _sigmoid(linear)
            diff = pred - float(target)
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


def _insar_gnss_placeholder_rows(samples: list[WindowSample]) -> list[list[str | float | None]]:
    rows: list[list[str | float | None]] = []
    for sample in samples[-12:]:
        rows.append(
            [
                sample.start_date.isoformat(),
                sample.end_date.isoformat(),
                None,
                None,
                None,
                "placeholder_pending_source",
                "Fase 2.2: VSR/SSR/NSR no disponible en catalogo actual.",
            ]
        )
    return rows


def run_international_estimation(
    as_of_date: date,
    lookback_days: int,
    window_days: int,
    stride_days: int,
    horizon_days: int,
    threshold_magnitude: float,
    min_magnitude: float,
    use_live_sources: bool,
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

    matrix, labels, mmax_targets, spans = _feature_matrix(dataset)
    split_idx = max(4, int(0.7 * len(dataset)))
    split_idx = min(split_idx, len(dataset) - 2)

    train_x = matrix[:split_idx]
    test_x = matrix[split_idx:]
    train_y_cls = labels[:split_idx]
    test_y_cls = labels[split_idx:]
    train_y_reg = mmax_targets[:split_idx]
    test_y_reg = mmax_targets[split_idx:]
    test_spans = spans[split_idx:]

    train_x_std, test_x_std, means, stds = _standardize(train_x, test_x)
    w_cls, b_cls = _train_logistic(train_x_std, train_y_cls)
    w_reg, b_reg = _train_linear(train_x_std, train_y_reg)

    cls_prob = _predict_logistic(test_x_std, w_cls, b_cls)
    reg_pred = _predict_linear(test_x_std, w_reg, b_reg)

    cls_metrics = _classification_metrics(test_y_cls, cls_prob)
    reg_metrics = _regression_metrics(test_y_reg, reg_pred)

    importance = _feature_importance(FEATURE_ORDER, w_cls, w_reg)
    ablation = _ablation_importance(test_x_std, test_y_cls, test_y_reg, w_cls, b_cls, w_reg, b_reg)
    ablation_rows = [
        [feature, impact]
        for feature, impact in sorted(zip(FEATURE_ORDER, ablation), key=lambda item: item[1], reverse=True)
    ]

    prediction_rows: list[list[str | float | int]] = []
    for span, y_true_prob, y_prob, y_true_mmax, y_mmax in zip(
        test_spans,
        test_y_cls,
        cls_prob,
        test_y_reg,
        reg_pred,
    ):
        prediction_rows.append(
            [
                span[0].isoformat(),
                span[1].isoformat(),
                span[2].isoformat(),
                int(y_true_prob),
                float(y_prob),
                float(y_true_mmax),
                float(y_mmax),
            ]
        )

    feature_rows: list[list[str | float]] = []
    for sample in dataset[-12:]:
        row: list[str | float] = [sample.start_date.isoformat(), sample.end_date.isoformat()]
        row.extend(float(sample.features.get(name, 0.0)) for name in FEATURE_ORDER)
        feature_rows.append(row)

    insar_gnss_rows = _insar_gnss_placeholder_rows(dataset)

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
        ["MSE", reg_metrics["mse"]],
        ["MAE", reg_metrics["mae"]],
        ["R2", reg_metrics["r2"]],
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
            "min_magnitude": min_magnitude,
            "use_live_sources": use_live_sources,
        },
        "event_count": len(events),
        "window_count": len(dataset),
        "training_windows": split_idx,
        "testing_windows": len(dataset) - split_idx,
        "source_table": source_table,
        "metrics_rows": metrics_rows,
        "importance_rows": importance,
        "ablation_rows": ablation_rows,
        "insar_gnss_rows": insar_gnss_rows,
        "similarity_rows": similarity_rows,
        "anomaly_reference_window": anomaly_reference_window,
        "insar_gnss_placeholder_policy": {
            "fields": ["vsr_mm_per_year", "ssr_mm_per_year", "nsr_mm_per_year"],
            "status": "placeholder_pending_source",
            "notes": "Agregar proveedor InSAR/GNSS para reemplazar placeholders.",
        },
    }
    out_path = _save_run(payload, as_of_date=as_of_date)

    return {
        "status": "ok",
        "message": "Modelo internacional ejecutado correctamente.",
        "source_table": source_table,
        "feature_rows": feature_rows,
        "insar_gnss_rows": insar_gnss_rows,
        "similarity_rows": similarity_rows,
        "anomaly_reference_window": anomaly_reference_window,
        "prediction_rows": prediction_rows,
        "metrics_rows": metrics_rows,
        "importance_rows": importance,
        "ablation_rows": ablation_rows,
        "probability_plot": {
            "x": [f"{row[0]}->{row[2]}" for row in prediction_rows],
            "y_prob": [float(row[4]) for row in prediction_rows],
            "y_true": [float(row[3]) for row in prediction_rows],
        },
        "mmax_plot": {
            "x": [f"{row[0]}->{row[2]}" for row in prediction_rows],
            "y_pred": [float(row[6]) for row in prediction_rows],
            "y_true": [float(row[5]) for row in prediction_rows],
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
        min_magnitude = gr.Number(value=3.0, label="Magnitud minima catalogo", minimum=1.0, maximum=7.0)
        use_live = gr.Checkbox(value=True, label="Usar APIs live (fallback local si falla)")

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
    gr.Markdown("### Fase 2.2: Placeholders InSAR/GNSS")
    insar_gnss_table = gr.Dataframe(
        headers=INSAR_GNSS_PLACEHOLDER_HEADERS,
        datatype=["str", "str", "number", "number", "number", "str", "str"],
        label="VSR/SSR/NSR (placeholder tecnico)",
        interactive=False,
    )

    gr.Markdown("### Fases 3-5: Target dual + modelo de clasificacion y regresion")
    prediction_table = gr.Dataframe(
        headers=[
            "window_start",
            "window_end",
            "target_end",
            "target_cls",
            "pred_prob",
            "target_mmax",
            "pred_mmax",
        ],
        datatype=["str", "str", "str", "number", "number", "number", "number"],
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
        min_mag_value: float,
        use_live_value: bool,
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
            min_magnitude=float(min_mag_value),
            use_live_sources=bool(use_live_value),
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

        status_text = (
            "### Estado\n"
            f"{payload.get('message', 'Ejecucion completada.')}\n\n"
            f"- Ventanas: {payload.get('window_count', 0)}\n"
            f"- Entrenamiento: {payload.get('training_windows', 0)}\n"
            f"- Prueba: {payload.get('testing_windows', 0)}\n"
            f"- Ventana anomala: {payload.get('anomaly_reference_window', '-')}\n"
            f"- Salida: {payload.get('storage_path', '-') }"
        )

        model_text = (
            "### Modelo (Fase 4)\n"
            "- Clasificacion: regresion logistica entrenada en ventanas historicas.\n"
            "- Regresion: modelo lineal para magnitud maxima esperada.\n"
            "- Validacion: pseudo-prospectiva con particion temporal 70/30.\n"
            "- Perdida: BCE implicita (clasificacion) y MSE (regresion)."
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
            min_magnitude,
            use_live,
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
