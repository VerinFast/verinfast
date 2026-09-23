"""Google Cloud cost and inventory collection.

Ports ``src/verinfast/cloud/gcp/``.

Already SDK-based (``google-cloud-compute``, ``-storage``, ``-monitoring``).
Same misreported upload source as Azure (`D4`).

v1 collected no GCP costs at all — only instances and storage. Worth
deciding whether v2 adds them.

New collectors: user activity from admin activity logs, load balancers from
forwarding rules (`F8`).
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import ArtifactResult, CloudAccount


class GcpProvider:
    """Google Cloud cost and inventory collection."""

    name = "gcp"

    def available(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("cloud.gcp.available")

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.costs")

    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.instances")

    def utilization(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.utilization")

    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.storage")

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.user_activity")

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.gcp.load_balancers")
