"""Git history: commits, authorship and per-file churn.

Ports src/verinfast/agent.py::parseRepo + formatGitHash.

Two things to fix on the way across:

- **Never ``git init`` the target.** v1 did, which creates a ``.git``
  directory in a user's tree when the path was not a repository (`D3`, `S12`).
- **One ``git log`` invocation, not six per commit.** v1 shelled out five
  times per hash plus a ``git show``; a delimited ``--format`` gets the same
  data in one pass (`D23`, `N13`).

The wire shape is fixed: numstat values stay strings, including ``"-"`` for
binary files, because that is what ATD parses.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, ScanTarget


class GitScanner:
    """Collect one repository's commit history."""

    artifact = Artifact.GIT

    def enabled(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("scanners.git.enabled")

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        raise NotImplementedError("scanners.git.run")
