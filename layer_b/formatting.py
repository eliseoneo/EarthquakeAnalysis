"""Formato datetime — Capa B."""

from __future__ import annotations

from datetime import datetime, timezone

DATETIME_UTC_FMT = "%Y-%m-%d %H:%M:%S"


def format_datetime_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(DATETIME_UTC_FMT)


def parse_datetime_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text, DATETIME_UTC_FMT)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
