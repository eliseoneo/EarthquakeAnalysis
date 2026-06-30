"""Análisis estadístico — correlación y comparación."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from layer_b.models import CorrelationResult


def _evidence_level(p_value: float | None, n: int) -> str:
    if p_value is None or n < 10:
        return "C"
    if p_value < 0.01 and n >= 30:
        return "A"
    if p_value < 0.05:
        return "B"
    return "C"


def compute_correlation(
    region_code: str,
    variable_x: str,
    x: list[float],
    variable_y: str,
    y: list[float],
    method: str,
) -> CorrelationResult:
    n = min(len(x), len(y))
    if n < 3:
        return CorrelationResult(
            region_code=region_code,
            variable_x=variable_x,
            variable_y=variable_y,
            method=method,
            coefficient=None,
            p_value=None,
            sample_size=n,
            evidence_level="C",
        )

    xa = np.array(x[:n], dtype=float)
    ya = np.array(y[:n], dtype=float)

    if method == "pearson":
        coef, p = stats.pearsonr(xa, ya)
    elif method == "spearman":
        coef, p = stats.spearmanr(xa, ya)
    elif method == "kendall":
        coef, p = stats.kendalltau(xa, ya)
    else:
        coef, p = None, None

    p_val = float(p) if p is not None and not np.isnan(p) else None
    coef_val = float(coef) if coef is not None and not np.isnan(coef) else None

    return CorrelationResult(
        region_code=region_code,
        variable_x=variable_x,
        variable_y=variable_y,
        method=method,
        coefficient=coef_val,
        p_value=p_val,
        sample_size=n,
        evidence_level=_evidence_level(p_val, n),
    )


def mann_whitney_test(a: list[float], b: list[float]) -> dict[str, Any]:
    if len(a) < 3 or len(b) < 3:
        return {"test": "mann_whitney", "statistic": None, "p_value": None, "evidence_level": "C"}
    stat, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "test": "mann_whitney",
        "statistic": float(stat),
        "p_value": float(p),
        "evidence_level": _evidence_level(float(p), len(a) + len(b)),
    }


def kolmogorov_smirnov_test(a: list[float], b: list[float]) -> dict[str, Any]:
    if len(a) < 3 or len(b) < 3:
        return {"test": "kolmogorov_smirnov", "statistic": None, "p_value": None, "evidence_level": "C"}
    result = stats.ks_2samp(a, b)
    return {
        "test": "kolmogorov_smirnov",
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "evidence_level": _evidence_level(float(result.pvalue), len(a) + len(b)),
    }


def permutation_test_mean_diff(a: list[float], b: list[float], n_perm: int = 500) -> dict[str, Any]:
    if len(a) < 3 or len(b) < 3:
        return {"test": "permutation", "statistic": None, "p_value": None, "evidence_level": "C"}
    observed = abs(np.mean(a) - np.mean(b))
    combined = np.array(a + b)
    n_a = len(a)
    count = 0
    rng = np.random.default_rng(42)
    for _ in range(n_perm):
        shuffled = rng.permutation(combined)
        diff = abs(np.mean(shuffled[:n_a]) - np.mean(shuffled[n_a:]))
        if diff >= observed:
            count += 1
    p = (count + 1) / (n_perm + 1)
    return {
        "test": "permutation",
        "statistic": float(observed),
        "p_value": float(p),
        "evidence_level": _evidence_level(float(p), len(a) + len(b)),
    }
