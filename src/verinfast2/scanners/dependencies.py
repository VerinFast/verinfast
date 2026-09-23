"""Dependency and licence inventory across ecosystems.

Ports ``src/verinfast/dependencies/ (walk.py + walkers/)``.

The walker decomposition was the right shape; keep it. Fix the interface —
v1's base ``Walker.initialize(command)`` and its subclasses'
``initialize(root_path)`` are not the same method (`D27`).

**Lockfile-first.** Running the scanned project's package manager executes
arbitrary code from its dependency graph. That is off by default and refused
outright in library mode (`S7`, `S8`); a lockfile covers most of it.

Output stays a flat array of entries with ``name`` and ``source`` required.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


class DependencyScanner:
    """Collect installed and declared dependencies."""

    artifact = Artifact.DEPENDENCIES

    def enabled(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("scanners.dependencies.enabled")

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        raise NotImplementedError("scanners.dependencies.run")
