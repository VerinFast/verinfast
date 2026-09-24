"""The types that cross VerinFast's public boundary.

Everything a caller passes in or gets back is defined here, so the public
surface is one file a reader can hold in their head. Nothing in this module
imports from anywhere else in ``verinfast2``; it is the bottom of the
dependency graph.

Pydantic rather than dataclasses, deliberately: ATD v3 is pydantic v2
throughout, so a :class:`ScanResult` drops straight into its ingest services
without a translation layer, and validation at the boundary is free.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["aws", "azure", "gcp"]


class Artifact(str, Enum):
    """Everything a scan can produce.

    The value is the upload-route name in :mod:`verinfast2.transport.paths`,
    so this enum and the route table cannot drift apart.
    """

    GIT = "git"
    SIZES = "sizes"
    STATS = "stats"
    FINDINGS = "findings"
    DEPENDENCIES = "dependencies"
    COSTS = "costs"
    INSTANCES = "instances"
    UTILIZATION = "utilization"
    STORAGE = "storage"
    USER_ACTIVITY = "user_activity"
    LOAD_BALANCERS = "load_balancers"
    SYSTEM_INFO = "system_info"


#: Artifacts produced per repository, in the order the agent uploads them.
REPO_ARTIFACTS: tuple[Artifact, ...] = (
    Artifact.GIT,
    Artifact.SIZES,
    Artifact.STATS,
    Artifact.FINDINGS,
    Artifact.DEPENDENCIES,
)

#: Artifacts produced per cloud account.
CLOUD_ARTIFACTS: tuple[Artifact, ...] = (
    Artifact.COSTS,
    Artifact.INSTANCES,
    Artifact.UTILIZATION,
    Artifact.STORAGE,
    Artifact.USER_ACTIVITY,
    Artifact.LOAD_BALANCERS,
)


class Outcome(str, Enum):
    """How one unit of work ended. Never inferred from an empty result."""

    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"


class ScanTarget(BaseModel):
    """One thing to scan: a remote repo, a local path, or a bare code sample."""

    model_config = ConfigDict(frozen=True)

    name: str
    path: Path | None = None
    url: str | None = None
    branch: str | None = None
    #: A directory of code with no git history and no remote — the ATD v3
    #: "scan this sample" case. Git collection is skipped rather than faked.
    is_sample: bool = False

    @property
    def identity(self) -> str:
        """A stable key that distinguishes this target from every other.

        ``name`` does **not**: it is the repository basename, so
        ``org-a/utils`` and ``org-b/utils`` are both ``utils``. Keying a
        clone directory or a cached file list on the name alone made the
        second target reuse the first's — scanning one repository's code and
        reporting it under the other's name.

        ATD still keys its repository rows on ``name``; this is for our own
        per-scan caches and directories, never for the wire.
        """
        source = self.url or (str(self.path) if self.path else "")
        digest = hashlib.sha256(
            f"{self.name}\x00{source}\x00{self.branch or ''}".encode("utf-8")
        ).hexdigest()[:12]
        return f"{self.name}:{digest}"


class CloudAccount(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Provider
    account: str
    profile: str | None = None
    start: date | None = None
    end: date | None = None


class ArtifactResult(BaseModel):
    """One artifact from one target.

    ``data`` is the payload in the shape ATD v3 expects; ``path`` is where it
    was written, when the caller asked for files. A caller can use either
    without the other.
    """

    artifact: Artifact
    target: str
    outcome: Outcome
    data: Any = None
    path: Path | None = None
    error: str | None = None
    duration_seconds: float | None = None
    #: Set when a cached result was served instead of a fresh scan.
    from_cache: bool = False


class ScanResult(BaseModel):
    """What a scan returns. The only thing a library caller needs.

    Writing files and uploading are separate, optional steps the caller
    drives; this object is complete without either.
    """

    scan_id: str | None = None
    report_id: str | int | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    targets: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactResult] = Field(default_factory=list)
    #: Non-fatal problems worth surfacing that did not fail an artifact.
    warnings: list[str] = Field(default_factory=list)

    def of(self, artifact: Artifact, target: str | None = None) -> list[ArtifactResult]:
        """Every result for *artifact*, optionally narrowed to one target."""
        return [
            a
            for a in self.artifacts
            if a.artifact is artifact and (target is None or a.target == target)
        ]

    def failed(self) -> list[ArtifactResult]:
        return [a for a in self.artifacts if a.outcome is Outcome.FAILED]

    @property
    def ok(self) -> bool:
        """True when nothing failed.

        Deliberately not "found no findings" — a clean scan and a scan that
        never ran must never look alike (`F18`).
        """
        return not self.failed()
