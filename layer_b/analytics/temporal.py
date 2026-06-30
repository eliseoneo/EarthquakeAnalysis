"""Dependencia temporal — correlación cruzada y rolling."""

from __future__ import annotations

from typing import Any

import numpy as np


def cross_correlation(x: list[float], y: list[float], max_lag: int = 7) -> dict[str, Any]:
    if len(x) < 5 or len(y) < 5:
        return {"method": "cross_correlation", "best_lag": None, "best_coef": None, "evidence_level": "C"}

    n = min(len(x), len(y))
    xa = np.array(x[:n]) - np.mean(x[:n])
    ya = np.array(y[:n]) - np.mean(y[:n])
    best_lag = 0
    best_coef = -1.0
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            xs, ys = xa[-lag:], ya[: n + lag]
        elif lag > 0:
            xs, ys = xa[: n - lag], ya[lag:]
        else:
            xs, ys = xa, ya
        if len(xs) < 3:
            continue
        denom = np.std(xs) * np.std(ys)
        coef = float(np.dot(xs - np.mean(xs), ys - np.mean(ys)) / (len(xs) * denom)) if denom else 0.0
        if abs(coef) > abs(best_coef):
            best_coef = coef
            best_lag = lag

    return {
        "method": "cross_correlation",
        "best_lag": best_lag,
        "best_coef": best_coef,
        "evidence_level": "B" if abs(best_coef) > 0.3 else "C",
    }


def rolling_correlation(x: list[float], y: list[float], window: int = 14) -> dict[str, Any]:
    if len(x) < window + 2 or len(y) < window + 2:
        return {"method": "rolling_correlation", "mean_coef": None, "evidence_level": "C"}

    n = min(len(x), len(y))
    coefs: list[float] = []
    for i in range(n - window + 1):
        xs = x[i : i + window]
        ys = y[i : i + window]
        if np.std(xs) == 0 or np.std(ys) == 0:
            continue
        coef = float(np.corrcoef(xs, ys)[0, 1])
        coefs.append(coef)

    if not coefs:
        return {"method": "rolling_correlation", "mean_coef": None, "evidence_level": "C"}

    mean_coef = float(np.mean(coefs))
    return {
        "method": "rolling_correlation",
        "mean_coef": mean_coef,
        "window": window,
        "evidence_level": "B" if abs(mean_coef) > 0.25 else "C",
    }


def granger_causality_placeholder(x: list[float], y: list[float]) -> dict[str, Any]:
    return {
        "method": "granger_causality",
        "status": "placeholder",
        "note": "ETAS/Granger no obligatorio en primera versión estable",
        "evidence_level": "C",
    }
