"""Security findings from a Semgrep-compatible engine.

Ports src/verinfast/code_scan.py::run_scan.

**Subprocess, not an in-process import.** Two independent reasons: a
``SystemExit`` from a vendored CLI must not reach a caller (`L6`), and the
engine is LGPL-2.1 — a process boundary is the posture nobody argues about.

**Do not use ``--config auto``.** It fetches rules from a registry whose
licence permits internal, non-competing, non-SaaS use only, and it makes
scans irreproducible. Ship a pinned, explicitly-licensed ruleset and record
its version in the artifact (`S18`).

See the wiki's *Semgrep Alternatives* for the engine and ruleset decision.
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
