"""Ley de Omori-Utsu — ajuste básico."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from layer_a.models import SeismicEvent


@dataclass(frozen=True)
class OmoriFit:
    k: float
    c: float
    p: float
    fit_quality: str
    observed_vs_expected_rate: float | None


def fit_omori_utsu(
    mainshock_time: datetime,
    aftershocks: list[SeismicEvent],
) -> OmoriFit:
    if len(aftershocks) < 5:
        return OmoriFit(1.0, 0.05, 1.0, "low", None)

    days = sorted(
        max(0.01, (e.datetime_utc - mainshock_time).total_seconds() / 86400)
        for e in aftershocks
    )
    n = len(days)
    k = n / math.log(max(days[-1], 1.0) + 0.05) if days else 1.0
    expected = k * math.log(days[-1] + 0.05) if days else 0
    ratio = n / expected if expected > 0 else None
    quality = "medium" if n >= 20 else "low"
    return OmoriFit(k=k, c=0.05, p=1.0, fit_quality=quality, observed_vs_expected_rate=ratio)
