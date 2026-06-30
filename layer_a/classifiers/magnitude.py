"""Clasificación por magnitud."""

from __future__ import annotations


def classify_magnitude(magnitude: float) -> str:
    if magnitude < 3.0:
        return "micro"
    if magnitude < 4.0:
        return "minor"
    if magnitude < 5.0:
        return "light"
    if magnitude < 6.0:
        return "moderate"
    if magnitude < 7.0:
        return "strong"
    if magnitude < 8.0:
        return "major"
    return "great"
