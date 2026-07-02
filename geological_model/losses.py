"""Funciones de pérdida espacial — docs/foco-geologico.md sección 4."""

from __future__ import annotations

import math
from typing import Iterable


def weighted_mse_mae(
    y_true: Iterable[float],
    y_pred: Iterable[float],
    weights: Iterable[float],
    alpha: float = 0.5,
) -> float:
    """Pérdida ponderada MSE-MAE para píxeles/eventos desbalanceados."""
    total_weight = 0.0
    loss = 0.0
    for target, pred, weight in zip(y_true, y_pred, weights, strict=True):
        w = max(0.0, float(weight))
        err = float(target) - float(pred)
        mse = err * err
        mae = abs(err)
        loss += w * (alpha * mse + (1.0 - alpha) * mae)
        total_weight += w
    if total_weight == 0.0:
        return 0.0
    return loss / total_weight


def gutenberg_richter_magnitude_weights(
    magnitudes: Iterable[float],
    b_value: float = 1.0,
    m_min: float = 4.0,
) -> list[float]:
    """Pesos STPiDN para magnitud según ley Gutenberg-Richter."""
    weights: list[float] = []
    for mag in magnitudes:
        delta_m = max(0.0, float(mag) - m_min)
        weights.append(math.exp(b_value * delta_m))
    return weights


def fault_distance_epicenter_weights(
    distances_km: Iterable[float],
    sigma_km: float = 25.0,
) -> list[float]:
    """Pesos STPiDN para epicentro según distancia a fallas."""
    return [
        math.exp(-((float(dist) / sigma_km) ** 2))
        for dist in distances_km
    ]


def stpidn_combined_weights(
    magnitudes: Iterable[float],
    distances_km: Iterable[float],
    b_value: float = 1.0,
    sigma_km: float = 25.0,
    magnitude_weight: float = 0.55,
) -> list[float]:
    """Combina pesos de magnitud y epicentro (STPiDN)."""
    mag_w = gutenberg_richter_magnitude_weights(magnitudes, b_value=b_value)
    dist_w = fault_distance_epicenter_weights(distances_km, sigma_km=sigma_km)
    combined: list[float] = []
    for mw, dw in zip(mag_w, dist_w, strict=True):
        combined.append(magnitude_weight * mw + (1.0 - magnitude_weight) * dw)
    return combined


def seismology_informed_mse_star(
    y_true: Iterable[float],
    y_pred: Iterable[float],
    reference_model: Iterable[float],
    base_weight: float = 1.0,
    failure_boost: float = 3.0,
) -> float:
    """MSE* penaliza zonas donde el modelo de referencia (p.ej. ETAS) falla."""
    weighted_errors: list[float] = []
    for target, pred, ref in zip(y_true, y_pred, reference_model, strict=True):
        ref_err = abs(float(target) - float(ref))
        pred_err = float(target) - float(pred)
        weight = base_weight + failure_boost * ref_err
        weighted_errors.append(weight * pred_err * pred_err)
    if not weighted_errors:
        return 0.0
    return sum(weighted_errors) / len(weighted_errors)
