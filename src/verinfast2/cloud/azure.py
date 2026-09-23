"""Azure cost and inventory collection.

Ports ``src/verinfast/cloud/azure/``.

Already SDK-based (``azure-mgmt-*``, ``azure-monitor-query``), so this is
mostly a reshape onto the provider interface.

Watch the upload source label: v1 reported Azure utilization uploads as
coming from AWS (`D4`).

New collectors: user activity from sign-in and audit logs, load balancers
from Load Balancer and Application Gateway (`F8`).
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import ArtifactResult, CloudAccount


class AzureProvider:
    """Azure cost and inventory collection."""

    name = "azure"

    def available(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("cloud.azure.available")

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.costs")

    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.instances")

    def utilization(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.utilization")

    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.storage")

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.user_activity")

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.azure.load_balancers")
