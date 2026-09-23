"""File inventory: sizes, line counts and extensions.

Ports src/verinfast/agent.py::parseRepo (get_raw_size, getloc, allowfile).

One traversal, not three (`D24`, `N12`), and binary files are not read line
by line to count newlines (`D26`, `N15`). The exclusion list comes from
config rather than a hardcoded set that ignores the one two files away
(`D10`).

The ``"."` root entry and the four ``metadata`` keys are load-bearing: ATD
lifts the root entry's size onto the repository row.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


class SizesScanner:
    """Collect file sizes, line counts and the file list."""

    artifact = Artifact.SIZES

    def enabled(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("scanners.sizes.enabled")

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        raise NotImplementedError("scanners.sizes.run")
