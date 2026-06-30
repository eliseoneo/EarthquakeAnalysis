"""Gutenberg-Richter b-value."""

from __future__ import annotations

import math
from dataclasses import dataclass

from layer_a.models import SeismicEvent


@dataclass(frozen=True)
class BValueResult:
    b_value: float | None
    a_value: float | None
    magnitude_of_completeness: float | None
    sample_size: int
    confidence_interval: tuple[float, float] | None
    confidence_level: str


def calculate_b_value(
    events: list[SeismicEvent],
    magnitude_threshold: float = 3.0,
) -> BValueResult:
    mags = sorted(
        (e.magnitude_preferred or e.magnitude for e in events if e.magnitude >= magnitude_threshold),
        reverse=True,
    )
    n = len(mags)
    if n < 10:
        return BValueResult(None, None, magnitude_threshold, n, None, "D")

    mc = magnitude_threshold
    mean_mag = sum(mags) / n
    b = math.log10(math.e) / (mean_mag - mc) if mean_mag > mc else None
    a = math.log10(n) + (b * mc) if b is not None else None

    confidence = "A" if n >= 50 else "B" if n >= 20 else "C"
    ci = None
    if b is not None and n >= 20:
        stderr = b / math.sqrt(n)
        ci = (b - 1.96 * stderr, b + 1.96 * stderr)

    return BValueResult(b, a, mc, n, ci, confidence)
