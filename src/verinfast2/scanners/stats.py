"""Code statistics: complexity, Halstead, maintainability.

Ports ``src/verinfast/agent.py::parseRepo (the modernmetric call)``.

**A subprocess, never an in-process import.** v1 did
``from modernmetric.__main__ import main as modernmetric`` and called it. That
function is a CLI entry point: it may ``sys.exit()``, and a ``SystemExit``
raised inside ATD v3's worker takes the worker down rather than failing one
artifact (`D18`, `L6`). ``python -m modernmetric`` is used rather than a
console script so the tool is found in whatever interpreter is running us,
installed or not on ``PATH``.

**Repo-relative paths, and that is the whole trick.** modernmetric echoes
back exactly the paths it was given, so the form of the filelist decides the
form of the output. v1 handed it absolute paths inside
``~/.verinfast/temp_repo``, and ATD rewrites ``temp_repo/...`` to ``./...`` on
ingest to compensate. Feed it ``./src/engine.py`` and that rewrite becomes a
no-op — and, more importantly, the row merges with the same file's ``sizes``
entry instead of creating a second one.

The subprocess runs with ``cwd=`` the target, so relative paths resolve
without anyone calling ``os.chdir`` (`L4`).

## Output shape

``{"files": {...}, "overall": {...}, "stats": {"mean"|"median"|"min"|"max"|
"sd": {...}}}`` — passed through untouched. ATD flattens ``overall.*`` onto
the repository and ``stats.<agg>.<prop>`` into columns, dropping keys it does
not know, so adding a metric upstream is safe and reshaping one here is not.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget
from verinfast2.scanners.sizes import relative_files

#: How modernmetric is invoked. ``-m`` rather than a console script: the
#: console script may not be on ``PATH`` in an embedded install, and
#: ``sys.executable`` guarantees the interpreter that has our dependencies.
MODULE: Final = "modernmetric"


def command(module_path: str, filelist: Path, output: Path) -> list[str]:
    """The subprocess argv. A list, so nothing is shell-quoted."""
    return [
        sys.executable,
        "-m",
        module_path,
        f"--file={filelist}",
        f"--output={output}",
    ]


def write_filelist(path: Path, files: list[str]) -> None:
    """modernmetric's input: ``[{"name": ..., "path": ...}, ...]``.

    ``path`` is repo-relative and ``./``-prefixed; ``name`` is the basename,
    which modernmetric uses only to pick a lexer.
    """
    entries = [{"name": rel.rsplit("/", 1)[-1], "path": rel} for rel in files]
    path.write_text(json.dumps(entries), encoding="utf-8")


class StatsScanner:
    """Collect modernmetric's per-file and rollup metrics."""

    artifact = Artifact.STATS

    def enabled(self, ctx: ScanContext) -> bool:
        return ctx.config.code.stats

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        if target.path is None:
            return self._result(
                target, Outcome.SKIPPED, error="no local path for this target"
            )

        files = ctx.files_in(
            target.name, lambda: relative_files(target.path, ctx.config.exclude)
        )
        if not files:
            # Not a failure and not an empty success: there was nothing to
            # measure, and that has to be distinguishable (`F18`).
            return self._result(target, Outcome.SKIPPED, error="no files to analyse")

        # Scratch lives in the scan's own work directory, never beside the
        # customer's code and never under ~ (`S12`, `S14`).
        scratch = ctx.work_dir / "stats" / target.name
        scratch.mkdir(parents=True, exist_ok=True)
        filelist = scratch / "filelist.json"
        output = scratch / "stats.json"
        write_filelist(filelist, files)

        try:
            completed = subprocess.run(
                command(MODULE, filelist, output),
                cwd=target.path,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=ctx.config.subprocess_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return self._result(
                target, Outcome.FAILED, error=f"could not run modernmetric: {exc}"
            )

        if completed.returncode != 0:
            return self._result(
                target,
                Outcome.FAILED,
                error=(
                    f"modernmetric exited {completed.returncode}: "
                    f"{completed.stderr.strip()[:500]}"
                ),
            )
        if not output.is_file():
            return self._result(
                target,
                Outcome.FAILED,
                error="modernmetric reported success but wrote no output file",
            )

        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return self._result(
                target, Outcome.FAILED, error=f"unreadable modernmetric output: {exc}"
            )

        return self._result(target, Outcome.OK, data=data)

    def _result(
        self,
        target: ScanTarget,
        outcome: Outcome,
        *,
        data: object = None,
        error: str | None = None,
    ) -> ArtifactResult:
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=outcome,
            data=data,
            error=error,
        )
