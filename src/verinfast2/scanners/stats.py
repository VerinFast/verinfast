"""Code statistics: complexity, Halstead, maintainability.

Ports ``src/verinfast/agent.py::parseRepo (the modernmetric call)``.

**A subprocess, never an in-process import.** v1 did
``from modernmetric.__main__ import main as modernmetric`` and called it. That
function is a CLI entry point: it may ``sys.exit()``, and a ``SystemExit``
raised inside ATD v3's worker takes the worker down rather than failing one
artifact (`D18`, `L6`).

**The console script, not ``python -m``** — and the difference is not
cosmetic. modernmetric analyses files through a ``multiprocessing.Pool``,
submitting ``pool.apply_async(process_file, ...)``. A function is pickled by
``__module__`` + ``__qualname__``, and under ``python -m modernmetric`` its
``__module__`` is ``"__main__"`` — which in a **spawned** child is the ``-m``
launcher, not modernmetric. The child raises ``AttributeError: Can't get
attribute 'process_file'``, the parent's ``async_result.get(timeout=...)``
times out, and ``__main__.py`` drops that file silently:

.. code-block:: python

    if file_result is None:
        continue

So every file times out and the run **exits 0 with an empty ``files`` map**,
taking ``files × file_timeout`` seconds to do it.

``fork`` hides this, which is why it never showed on Linux. macOS defaults to
``spawn``, so on the platform most customer laptops run, stats were silently
empty. Invoked through the console script, ``modernmetric.__main__`` is an
ordinary imported module, the qualified name resolves in the child, and it
works under either start method — verified both ways.

:func:`resolve_tool` looks beside ``sys.executable`` first so a virtualenv's
own script wins over anything earlier on ``PATH``, and falls back to ``-m``
only when no console script exists. :meth:`StatsScanner._check_coverage` is
the safety net for that fallback and for any future version of this bug: a
run that analysed none of the files it was given is a **failure**, not an
empty result.

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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget
from verinfast2.scanners.sizes import relative_files

#: The tool's name, as both a console script and an importable module.
MODULE: Final = "modernmetric"


def resolve_tool(name: str = MODULE) -> list[str] | None:
    """How to launch *name*: the console script if there is one, else ``-m``.

    The console script is preferred because it is the only form that works
    under a ``spawn`` start method — see the module docstring. A virtualenv's
    own script is looked for first so it wins over an older copy earlier on
    ``PATH``.

    Returns None when the tool is not installed at all.
    """
    bindir = Path(sys.executable).parent
    for candidate in (bindir / name, bindir / f"{name}.exe"):
        if candidate.is_file():
            return [str(candidate)]
    found = shutil.which(name)
    if found:
        return [found]
    # No console script. `-m` still runs, and still works wherever the start
    # method is `fork`; `_check_coverage` catches it where it does not.
    try:
        __import__(name)
    except ImportError:
        return None
    return [sys.executable, "-m", name]


def command(
    launcher: list[str],
    filelist: Path,
    output: Path,
    *,
    file_timeout: int,
    cache_dir: Path,
) -> list[str]:
    """The subprocess argv. A list, so nothing is shell-quoted.

    ``--cache-dir`` is passed as an **absolute** path deliberately.
    modernmetric builds its cache path as ``Path(Path.home(), cache_dir,
    cache_db)``, and pathlib discards everything left of an absolute
    component — so an absolute directory is the only way to stop it writing a
    SQLite file into the user's home directory, which v2 does not do (`L7`,
    `S15`).

    ``--file_timeout`` is passed explicitly because the default is 180
    seconds **per file**; a run that is going to produce nothing should say so
    in seconds, not in hours.
    """
    return [
        *launcher,
        f"--file={filelist}",
        f"--output={output}",
        f"--file_timeout={file_timeout}",
        f"--cache-dir={cache_dir}",
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

        launcher = resolve_tool()
        if launcher is None:
            return self._result(
                target, Outcome.FAILED, error=f"{MODULE} is not installed"
            )

        # Scratch lives in the scan's own work directory, never beside the
        # customer's code and never under ~ (`S12`, `S14`).
        scratch = ctx.scratch_for(target.name, "stats")
        filelist = scratch / "filelist.json"
        output = scratch / "stats.json"
        cache_dir = (ctx.config.cache_dir or ctx.work_dir / "stats-cache").resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        write_filelist(filelist, files)

        try:
            completed = subprocess.run(
                command(
                    launcher,
                    filelist,
                    output,
                    file_timeout=int(ctx.config.stats_file_timeout_seconds),
                    cache_dir=cache_dir,
                ),
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

        problem = self._check_coverage(ctx, target, files, data)
        if problem is not None:
            return self._result(target, Outcome.FAILED, error=problem)

        return self._result(target, Outcome.OK, data=data)

    def _check_coverage(
        self,
        ctx: ScanContext,
        target: ScanTarget,
        sent: list[str],
        data: object,
    ) -> str | None:
        """Refuse to pass off a silently empty run as a clean result.

        modernmetric drops a file it could not process and carries on, so an
        empty ``files`` map is indistinguishable from "analysed everything
        and found nothing" — the `F18` problem, inside a tool we shell out
        to. Zero analysed from a non-empty list is a failure; a partial run
        is a warning.

        Returns an error message, or None when the run is acceptable.
        """
        if not isinstance(data, dict):
            return "engine output was not a JSON object"
        analysed = data.get("files")
        count = len(analysed) if isinstance(analysed, dict) else 0

        if count == 0:
            return (
                f"{MODULE} exited cleanly but analysed none of the "
                f"{len(sent)} file(s) it was given. It drops a file it cannot "
                "process without failing, so this would otherwise look like a "
                "clean scan."
            )
        if count < len(sent):
            ctx.log.warning(
                "%s: %s analysed %d of %d files; the rest were dropped",
                target.name,
                MODULE,
                count,
                len(sent),
            )
        return None

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
