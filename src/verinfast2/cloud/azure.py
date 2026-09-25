"""Azure cost and inventory collection.

Ports ``src/verinfast/cloud/azure/``.

Already SDK-based (``azure-mgmt-*``, ``azure-monitor-query`` for logs and
``azure-monitor-querymetrics`` for metrics), so this is mostly a reshape onto
the provider interface.

Sources when these are written: sign-in and audit logs for user activity; Load Balancer plus Application Gateway for balancers.

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


class AzureProvider:
    """Azure cost and inventory collection."""

    name = "azure"

    def available(self, ctx: ScanContext) -> bool:
        """Whether the Azure SDK is importable."""
        # find_spec raises rather than returning None when a *parent*
        # package is missing, which is the ordinary case here: no `azure`,
        # no `google` namespace at all. "Is it installed" must answer False,
        # never raise -- the orchestrator asks this before it can report
        # anything, so a raise here loses all six artifacts.
        for module in ["azure.identity", "azure.mgmt.compute"]:
            try:
                if importlib.util.find_spec(module) is None:
                    return False
            except (ImportError, ValueError):
                return False
        return True

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.COSTS, account, NOT_PORTED)

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
