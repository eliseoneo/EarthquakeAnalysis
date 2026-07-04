"""Persistencia de corridas para Capa C (runs + latest + indice)."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from layer_c.paths import LAYER_C_ROOT, PERSISTENCE_DIR


RUNS_DIR = PERSISTENCE_DIR / "runs"
LATEST_DIR = PERSISTENCE_DIR / "latest"
INDEX_PATH = PERSISTENCE_DIR / "index.jsonl"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy_artifact(src: Path, dst: Path) -> Path | None:
    if not src.exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def persist_run(summary: dict[str, Any], artifact_paths: dict[str, Path]) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_DIR / run_id

    _ensure_dir(run_dir)
    _ensure_dir(LATEST_DIR)
    _ensure_dir(INDEX_PATH.parent)

    copied: dict[str, str] = {}
    for key, src_path in artifact_paths.items():
        run_target = run_dir / src_path.name
        latest_target = LATEST_DIR / src_path.name
        copied_run = _copy_artifact(src_path, run_target)
        if copied_run is None:
            continue
        _copy_artifact(src_path, latest_target)
        copied[key] = str(copied_run.relative_to(LAYER_C_ROOT))

    summary_payload = dict(summary)
    summary_payload["persistence"] = {
        "run_id": run_id,
        "run_dir": str(run_dir.relative_to(LAYER_C_ROOT)),
        "latest_dir": str(LATEST_DIR.relative_to(LAYER_C_ROOT)),
        "artifacts": copied,
    }

    run_summary = run_dir / "summary.json"
    latest_summary = LATEST_DIR / "summary.json"
    run_summary.write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")
    latest_summary.write_text(json.dumps(summary_payload, indent=2, default=str), encoding="utf-8")

    with INDEX_PATH.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "run_id": run_id,
                    "created_at_utc": now.isoformat(),
                    "summary": str(run_summary.relative_to(LAYER_C_ROOT)),
                    "artifacts": copied,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return {
        "run_id": run_id,
        "run_dir": str(run_dir.relative_to(LAYER_C_ROOT)),
        "latest_dir": str(LATEST_DIR.relative_to(LAYER_C_ROOT)),
        "summary": str(run_summary.relative_to(LAYER_C_ROOT)),
        "index": str(INDEX_PATH.relative_to(LAYER_C_ROOT)),
    }