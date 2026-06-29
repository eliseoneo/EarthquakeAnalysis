#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _run(script_name: str, extra_args: list[str] | None = None) -> int:
    command = [sys.executable, str(SCRIPT_DIR / script_name)]
    if extra_args:
        command.extend(extra_args)
    print(f"\n>>> {' '.join(command)}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta evaluaciones de Fase 1, Fase 2 y Fase 3."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Evalua datos reales ademas de fixtures sinteticos.",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=95.0,
        help="Umbral minimo de cobertura para Fase 3.",
    )
    args = parser.parse_args()

    phase_args = ["--full"] if args.full else []
    phase3_args = [*phase_args, "--fail-under", str(args.fail_under)]

    results = {
        "phase1": _run("evaluate_phase1.py", phase_args),
        "phase2": _run("evaluate_phase2.py", phase_args),
        "phase3": _run("evaluate_phase3.py", phase3_args),
    }

    print("\nSummary")
    for phase, code in results.items():
        print(f"- {phase}: {'PASS' if code == 0 else 'FAIL'}")

    if any(code != 0 for code in results.values()):
        print("\nOverall evaluation failed.")
        return 1

    print("\nOverall evaluation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
