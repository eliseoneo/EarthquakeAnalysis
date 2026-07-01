from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_ROOT = ROOT / "storage" / "venezuela"


@dataclass(frozen=True)
class ProjectionPaths:
    docs_json: Path
    docs_csv: Path
    store_json: Path
    store_csv: Path
    latest_json: Path
    latest_csv: Path
    index_jsonl: Path


@dataclass(frozen=True)
class VerificationPaths:
    docs_json: Path
    store_json: Path
    latest_json: Path
    index_jsonl: Path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    _ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    tmp.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def projection_paths(as_of_date: date) -> ProjectionPaths:
    day = as_of_date.isoformat()
    y = f"{as_of_date.year:04d}"
    m = f"{as_of_date.month:02d}"
    d = f"{as_of_date.day:02d}"

    docs_json = ROOT / "docs" / f"venezuela_projection_{day}.json"
    docs_csv = ROOT / "docs" / f"venezuela_projection_{day}_events.csv"

    base = PERSISTENCE_ROOT / "projections" / y / m / d
    store_json = base / "projection.json"
    store_csv = base / "events.csv"

    latest_json = PERSISTENCE_ROOT / "projections" / "latest" / "projection.json"
    latest_csv = PERSISTENCE_ROOT / "projections" / "latest" / "events.csv"
    index_jsonl = PERSISTENCE_ROOT / "indices" / "projections.jsonl"

    return ProjectionPaths(
        docs_json=docs_json,
        docs_csv=docs_csv,
        store_json=store_json,
        store_csv=store_csv,
        latest_json=latest_json,
        latest_csv=latest_csv,
        index_jsonl=index_jsonl,
    )


def verification_paths(verification_date: date) -> VerificationPaths:
    day = verification_date.isoformat()
    y = f"{verification_date.year:04d}"
    m = f"{verification_date.month:02d}"
    d = f"{verification_date.day:02d}"

    docs_json = ROOT / "docs" / f"venezuela_daily_effectiveness_{day}.json"

    base = PERSISTENCE_ROOT / "verifications" / y / m / d
    store_json = base / "verification.json"

    latest_json = PERSISTENCE_ROOT / "verifications" / "latest" / "verification.json"
    index_jsonl = PERSISTENCE_ROOT / "indices" / "verifications.jsonl"

    return VerificationPaths(
        docs_json=docs_json,
        store_json=store_json,
        latest_json=latest_json,
        index_jsonl=index_jsonl,
    )


def write_projection_artifacts(
    as_of_date: date,
    report: dict[str, Any],
    csv_content: str,
) -> ProjectionPaths:
    paths = projection_paths(as_of_date)

    report_with_storage = dict(report)
    report_with_storage["persistence"] = {
        "store_json": str(paths.store_json.relative_to(ROOT)),
        "store_csv": str(paths.store_csv.relative_to(ROOT)),
        "latest_json": str(paths.latest_json.relative_to(ROOT)),
        "latest_csv": str(paths.latest_csv.relative_to(ROOT)),
    }

    report_text = json.dumps(report_with_storage, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_text(paths.docs_json, report_text)
    _atomic_write_text(paths.store_json, report_text)

    _atomic_write_text(paths.docs_csv, csv_content)
    _atomic_write_text(paths.store_csv, csv_content)

    _atomic_write_text(paths.latest_json, report_text)
    _atomic_write_text(paths.latest_csv, csv_content)

    _append_jsonl(
        paths.index_jsonl,
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "docs_json": str(paths.docs_json.relative_to(ROOT)),
            "docs_csv": str(paths.docs_csv.relative_to(ROOT)),
            "store_json": str(paths.store_json.relative_to(ROOT)),
            "store_csv": str(paths.store_csv.relative_to(ROOT)),
        },
    )

    return paths


def write_verification_artifact(
    verification_date: date,
    report: dict[str, Any],
) -> VerificationPaths:
    paths = verification_paths(verification_date)

    report_with_storage = dict(report)
    report_with_storage["persistence"] = {
        "store_json": str(paths.store_json.relative_to(ROOT)),
        "latest_json": str(paths.latest_json.relative_to(ROOT)),
    }

    report_text = json.dumps(report_with_storage, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_text(paths.docs_json, report_text)
    _atomic_write_text(paths.store_json, report_text)
    _atomic_write_text(paths.latest_json, report_text)

    _append_jsonl(
        paths.index_jsonl,
        {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "verification_date": verification_date.isoformat(),
            "docs_json": str(paths.docs_json.relative_to(ROOT)),
            "store_json": str(paths.store_json.relative_to(ROOT)),
        },
    )

    return paths


def latest_verification_report() -> dict[str, Any] | None:
    latest_path = PERSISTENCE_ROOT / "verifications" / "latest" / "verification.json"
    if latest_path.exists():
        try:
            data = json.loads(latest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    legacy_docs = sorted((ROOT / "docs").glob("venezuela_daily_effectiveness_*.json"))
    if not legacy_docs:
        return None
    try:
        data = json.loads(legacy_docs[-1].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
