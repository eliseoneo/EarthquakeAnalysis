"""Clasificación de mecanismo focal por rake."""

from __future__ import annotations


def classify_focal_mechanism(rake: float | None) -> str:
    if rake is None:
        return "unknown"
    normalized = ((rake + 180) % 360) - 180
    if abs(normalized) <= 30 or abs(abs(normalized) - 180) <= 30:
        return "strike_slip"
    if -120 <= normalized <= -60:
        return "normal"
    if 60 <= normalized <= 120:
        return "reverse_thrust"
    return "oblique"
