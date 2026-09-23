"""A machine-readable account of what actually happened.

New in v2 (`F18`). v1 gave a caller no way to tell "clean scan, no findings"
apart from "the scan never ran" — both produced an empty findings file. ATD
v3 needs to distinguish them.
"""

from __future__ import annotations

from typing import Any

from verinfast2.models import Outcome, ScanResult


def run_summary(result: ScanResult) -> dict[str, Any]:
    """What ran, what was skipped, what failed, and why."""
    by_outcome: dict[str, list[str]] = {o.value: [] for o in Outcome}
    for a in result.artifacts:
        by_outcome[a.outcome.value].append(f"{a.target}:{a.artifact.value}")
    return {
        "scan_id": result.scan_id,
        "report_id": result.report_id,
        "targets": result.targets,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "ok": result.ok,
        "counts": {k: len(v) for k, v in by_outcome.items()},
        "artifacts": by_outcome,
        "errors": [
            {"target": a.target, "artifact": a.artifact.value, "error": a.error}
            for a in result.failed()
        ],
        "warnings": result.warnings,
    }
