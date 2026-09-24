"""Google Cloud cost and inventory collection.

Ports ``src/verinfast/cloud/gcp/``.

Nothing here collects yet. Every artifact returns SKIPPED with a reason
rather than raising: the orchestrator runs all three providers over whatever
the config names, and one unported provider must not cost a scan the
provider that does work (`F19`). A SKIPPED result also keeps the distinction
`F18` is about -- this is "never ran", and it must not be filed as "found
nothing".

Sources when these are written: admin activity audit logs for user activity; forwarding rules for balancers.

The SDK is imported inside the methods, never at module scope: the clouds
are moving behind extras and ``cloud/__init__`` imports all three providers.
"""

from __future__ import annotations

import importlib.util

from verinfast2.cloud.base import skipped
from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, CloudAccount

#: Ported artifacts are a mechanical port of v1; the two new ones are real
#: collection work with no v1 code behind them. Neither is in this change.
NOT_PORTED = "not ported from v1 yet"
NOT_WRITTEN = "not written yet -- new in v2, no v1 source to port"


class GcpProvider:
    """Google Cloud cost and inventory collection."""

    name = "gcp"

    def available(self, ctx: ScanContext) -> bool:
        """Whether the Google Cloud SDK is importable."""
        # find_spec raises rather than returning None when a *parent*
        # package is missing, which is the ordinary case here: no `azure`,
        # no `google` namespace at all. "Is it installed" must answer False,
        # never raise -- the orchestrator asks this before it can report
        # anything, so a raise here loses all six artifacts.
        for module in ["google.cloud.compute_v1"]:
            try:
                if importlib.util.find_spec(module) is None:
                    return False
            except (ImportError, ValueError):
                return False
        return True

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(
            Artifact.COSTS,
            account,
            "v1 collected no GCP costs; see the wiki before adding them",
        )

    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.INSTANCES, account, NOT_PORTED)

    def utilization(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.UTILIZATION, account, NOT_PORTED)

    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.STORAGE, account, NOT_PORTED)

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.USER_ACTIVITY, account, NOT_WRITTEN)

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.LOAD_BALANCERS, account, NOT_WRITTEN)
