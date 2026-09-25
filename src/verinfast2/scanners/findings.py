"""Security findings, from Opengrep over the ruleset VerinFast ships.

Ports ``src/verinfast/code_scan.py::run_scan``.

**The engine is Opengrep**, the LGPL-2.1 community fork of Semgrep CE. It is
rule- and output-compatible, so ATD v3's findings ingest is unaffected, and
it ships as a binary rather than a PyPI package — which removes the 44
Semgrep-only packages from the runtime closure outright.

**Subprocess, not an in-process import.** v1 did ``import
semgrep.commands.scan as semgrep_scan`` and called ``semgrep_scan.scan()``,
so a ``SystemExit`` from a vendored CLI reached the caller (`L6`, `D18`).
Opengrep being a binary makes a process boundary the only option anyway, and
it is the unambiguous posture for an LGPL engine.

**Never ``--config auto``.** Those registry rules are licensed for internal,
non-competing, non-SaaS use only, and fetching them at scan time makes a scan
irreproducible. :mod:`verinfast2.scanners.ruleset` points at the vendored,
MIT-licensed, revision-pinned rules instead, and its ``provenance`` rides
along in the artifact so a finding set stays explainable months later
(`S18`).

## Findings are not truncated here

The artifact carries the matched source lines in full. Cutting them is the
upload boundary's job — :func:`verinfast2.transport.payloads.truncate_findings`
— because the local HTML report wants the untruncated text and the same
object must serve both. v1 truncated in place and could not (`D19`).

## Exit codes

The engine exits 0 with no findings and 1 with findings; neither is an error.
Anything else is. v1 did not distinguish them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Final

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget
from verinfast2.scanners.ruleset import (
    ENGINE,
    engine_command,
    engine_env,
    load_ruleset,
)

#: Exit codes that mean the engine ran. 1 is "found something", not a failure.
RAN: Final[frozenset[int]] = frozenset({0, 1})

#: Where the ruleset's provenance is recorded in the artifact. Namespaced so
#: it cannot collide with a key the engine emits; ATD's ingest models are
#: ``extra="allow"``, so an unknown top-level key rides along untouched.
PROVENANCE_KEY: Final = "verinfast_ruleset"


def engine_available(engine: str = ENGINE) -> str | None:
    """The engine's path, or None if it is not installed."""
    return shutil.which(engine)


class FindingsScanner:
    """Collect security findings for one repository.

    Args:
        engine: binary name or path. Injected in tests; defaults to whatever
            :data:`~verinfast2.scanners.ruleset.ENGINE` names on ``PATH``.
        rules_dir: override the shipped ruleset, for tests.
    """

    artifact = Artifact.FINDINGS

    def __init__(self, engine: str = ENGINE, rules_dir: Path | None = None) -> None:
        self._engine = engine
        self._rules_dir = rules_dir

    def enabled(self, ctx: ScanContext) -> bool:
        return ctx.config.code.findings

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        if target.path is None:
            return self._skip(target, "no local path for this target")

        try:
            ruleset = load_ruleset(self._rules_dir)
        except (FileNotFoundError, ValueError) as exc:
            return self._failed(target, str(exc))

        if engine_available(self._engine) is None:
            # Not a skip: findings were asked for and there are none, which
            # must not look like a clean scan (`F18`). The operator has an
            # install problem and needs to hear about it.
            return self._failed(
                target,
                f"{self._engine} is not installed or not on PATH; no findings "
                "were collected",
            )

        output = (
            ctx.scratch_for(target.name, "findings", key=target.identity)
            / "findings.json"
        )
        # Scan `.`, not an absolute path: the engine puts the path it was
        # given into every finding, and an absolute one leaks the scanning
        # machine's layout into ATD (`S3`). `cwd` makes `.` the target.
        argv = engine_command(Path("."), output, ruleset, engine=self._engine)

        try:
            completed = subprocess.run(
                argv,
                cwd=target.path,
                env=engine_env(),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=ctx.config.subprocess_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._failed(
                target,
                f"{self._engine} exceeded "
                f"{ctx.config.subprocess_timeout_seconds:.0f}s and was killed",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return self._failed(target, f"could not run {self._engine}: {exc}")

        if completed.returncode not in RAN:
            return self._failed(
                target,
                f"{self._engine} exited {completed.returncode}: "
                f"{completed.stderr.strip()[:500]}",
            )

        if not output.is_file():
            return self._failed(
                target,
                f"{self._engine} exited {completed.returncode} but wrote no "
                "output file",
            )

        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return self._failed(target, f"unreadable engine output: {exc}")

        if not isinstance(data, dict):
            return self._failed(target, "engine output was not a JSON object")

        self._record_engine_errors(ctx, target, data)
        data[PROVENANCE_KEY] = ruleset.provenance

        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.OK,
            data=data,
        )

    def _record_engine_errors(
        self, ctx: ScanContext, target: ScanTarget, data: dict[str, Any]
    ) -> None:
        """Surface per-file parse errors instead of letting them pass silently.

        The engine reports a file it could not parse in ``errors`` and carries
        on. That is the right behaviour, but a scan where half the tree failed
        to parse and a scan that genuinely found nothing produce the same
        empty ``results`` — so the count is logged (`F18`).
        """
        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            ctx.log.warning(
                "%s: %s reported %d file-level error(s) during the scan",
                target.name,
                self._engine,
                len(errors),
            )

    def _skip(self, target: ScanTarget, why: str) -> ArtifactResult:
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.SKIPPED,
            error=why,
        )

    def _failed(self, target: ScanTarget, why: str) -> ArtifactResult:
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.FAILED,
            error=why,
        )
