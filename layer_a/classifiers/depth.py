"""Clasificación por profundidad."""

from __future__ import annotations


def classify_depth(depth_km: float) -> str:
    if depth_km <= 10:
        return "shallow_critical"
    if depth_km <= 30:
        return "shallow_crustal"
    if depth_km <= 70:
        return "intermediate_shallow"
    if depth_km <= 300:
        return "intermediate"
    return "deep"
