"""Code statistics: complexity, Halstead, maintainability.

Ports ``src/verinfast/agent.py::parseRepo (the modernmetric call)``.

Run modernmetric as a subprocess or behind an adapter — never by calling
its ``__main__.main()`` in-process, which is how a ``SystemExit`` ends up in
ATD v3's worker (`D18`, `L6`).

Emit repo-relative paths. v1 emitted paths containing ``temp_repo/`` and ATD
rewrites them; get it right here and that rewrite becomes a no-op.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


class StatsScanner:
    """Collect modernmetric's per-file and rollup metrics."""

    artifact = Artifact.STATS

    def enabled(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("scanners.stats.enabled")

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        raise NotImplementedError("scanners.stats.run")
