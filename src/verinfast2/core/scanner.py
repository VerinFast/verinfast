"""The orchestrator: run the requested scanners over the requested targets.

Deliberately thin. v1's ``Agent`` was 929 lines and did orchestration, git
parsing, filesystem walking, cloud dispatch and HTTP upload on one class
(`N6`, `N7`). Here each of those is somebody else's module, and this file
only decides what runs and collects what comes back.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from verinfast2.config.schema import ScanConfig
from verinfast2.core.context import ProgressFn, ScanContext, scan_context
from verinfast2.models import ArtifactResult, Outcome, ScanResult, ScanTarget


class Scanner:
    """Run one scan.

    Importing this module does nothing observable: no argv, no prompt, no
    home directory, no log file (`L1`).

        >>> from verinfast2 import ScanConfig, Scanner
        >>> result = Scanner(ScanConfig(embedded=True)).scan_path("/tmp/sample")

    Two instances may run concurrently over different trees: state lives in
    a per-scan :class:`~verinfast2.core.context.ScanContext`, never in module
    globals, and no scanner changes the working directory (`L3`, `L4`).
    """

    def __init__(
        self,
        config: ScanConfig,
        *,
        log: logging.Logger | None = None,
        progress: ProgressFn | None = None,
    ) -> None:
        self.config = config.for_library() if config.embedded else config
        self._log = log or logging.getLogger("verinfast")
        self._progress = progress

    # -- Entry points ---------------------------------------------------

    def scan(self) -> ScanResult:
        """Scan everything the config names: targets, then cloud accounts."""
        with scan_context(self.config, log=self._log, progress=self._progress) as ctx:
            result = ScanResult(report_id=self.config.report_id)
            for target in self.config.targets:
                result.targets.append(target.name)
                result.artifacts.extend(self._scan_target(ctx, target))
            for account in self.config.cloud:
                result.artifacts.extend(self._scan_cloud(ctx, account))
            result.finished_at = datetime.now(timezone.utc)
            return result

    def scan_path(self, path: str, *, name: str | None = None) -> ScanResult:
        """Scan one directory of code.

        The ATD v3 case: a code sample with no git history and no remote.
        Git collection is skipped rather than synthesised, and nothing is
        written into the scanned tree — no ``git init`` (`F5`, `L8`, `S12`).
        """
        from pathlib import Path

        target = ScanTarget(
            name=name or Path(path).name, path=Path(path), is_sample=True
        )
        config = self.config.model_copy(update={"targets": [target]})
        return Scanner(config, log=self._log, progress=self._progress).scan()

    # -- Internals ------------------------------------------------------

    def _scan_target(
        self, ctx: ScanContext, target: ScanTarget
    ) -> list[ArtifactResult]:
        """Run every enabled code scanner over one target.

        A failure in one scanner must not abort the others, and must be
        reported rather than swallowed (`F19`, `N10`).

        Raises:
            NotImplementedError: the scanner registry is not wired yet.
        """
        raise NotImplementedError("core.scanner.Scanner._scan_target")

    def _scan_cloud(self, ctx: ScanContext, account) -> list[ArtifactResult]:
        """Collect every artifact for one cloud account.

        Raises:
            NotImplementedError: the provider registry is not wired yet.
        """
        raise NotImplementedError("core.scanner.Scanner._scan_cloud")


def skipped(artifact, target: str, why: str) -> ArtifactResult:
    """A scanner that declined to run, with a reason. Never a silent empty."""
    return ArtifactResult(
        artifact=artifact, target=target, outcome=Outcome.SKIPPED, error=why
    )
