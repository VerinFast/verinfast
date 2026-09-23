"""Security findings, from Opengrep over the ruleset VerinFast ships.

Ports ``src/verinfast/code_scan.py::run_scan``.

**The engine is Opengrep**, the LGPL-2.1 community fork of Semgrep CE. It is
rule- and output-compatible, so ATD v3's findings ingest is unaffected, and
it ships as a binary rather than a PyPI package — which removes the 44
Semgrep-only packages from the runtime closure outright.

**Subprocess, not an in-process import.** A ``SystemExit`` from a vendored
CLI must not reach a caller (`L6`), and a process boundary is the
unambiguous posture for an LGPL engine. Opengrep being a binary makes this
the only option anyway.

**Never ``--config auto``.** Those registry rules are licensed for internal,
non-competing, non-SaaS use only, and fetching them at scan time makes a
scan irreproducible. :mod:`verinfast2.scanners.ruleset` points at the
vendored, MIT-licensed, revision-pinned rules instead, and its
``provenance`` goes into the artifact so a finding set stays explainable
(`S18`).

Build the subprocess environment with
:func:`~verinfast2.scanners.ruleset.engine_env` — Opengrep's bundled
interpreter dies on a non-UTF-8 locale, and shipped rules contain non-ASCII
characters.

See the wiki's *Semgrep Alternatives* for how the engine was chosen.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


class FindingsScanner:
    """Collect security findings for one repository."""

    artifact = Artifact.FINDINGS

    def enabled(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("scanners.findings.enabled")

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        raise NotImplementedError("scanners.findings.run")
