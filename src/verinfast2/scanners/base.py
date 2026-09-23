"""One shape for every code scanner.

v1 had five stages inlined into ``Agent.parseRepo`` with no common
interface, so adding one meant editing a 929-line file. Here a scanner is
anything matching :class:`CodeScanner`, and the registry below is the only
place that changes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


@runtime_checkable
class CodeScanner(Protocol):
    """Collect one artifact from one target.

    Implementations must:

    - never change the working directory — pass ``cwd=`` to subprocesses
      instead (`L4`);
    - never modify the tree they are scanning (`S12`);
    - return a failed :class:`~verinfast2.models.ArtifactResult` rather than
      raising, so one scanner's failure cannot abort the rest (`F19`);
    - be safe to run concurrently with other scanners on other targets.
    """

    #: Which artifact this produces.
    artifact: Artifact

    def enabled(self, ctx: ScanContext) -> bool:
        """Whether this should run at all, given config and target."""
        ...

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        """Collect the artifact. Returns a result; does not raise."""
        ...


def registry() -> dict[Artifact, type]:
    """Every code scanner, keyed by the artifact it produces.

    Imported here rather than at module scope so this module stays importable
    by a scanner that wants the ``CodeScanner`` protocol without a cycle.

    An artifact missing from this mapping is not an error — it means no
    scanner is ported yet, and the orchestrator records a skip with that
    reason rather than a silent empty result (`F18`).
    """
    from verinfast2.scanners.git import GitScanner
    from verinfast2.scanners.sizes import SizesScanner

    return {
        Artifact.GIT: GitScanner,
        Artifact.SIZES: SizesScanner,
    }
