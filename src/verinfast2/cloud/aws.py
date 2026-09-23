"""Amazon Web Services cost and inventory collection.

Ports ``src/verinfast/cloud/aws/``.

**Use ``boto3``, not the ``aws`` CLI.** boto3 is already a dependency, and
the CLI path builds its command as a shell string with a config-supplied
profile name interpolated into it (`D9`, `S9`). Dropping the shell-out also
removes the "is the CLI installed" preflight for AWS.

New collectors: user activity from CloudTrail, load balancers from
ELB/ALB/NLB (`F8`).
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.models import ArtifactResult, CloudAccount


class AwsProvider:
    """Amazon Web Services cost and inventory collection."""

    name = "aws"

    def available(self, ctx: ScanContext) -> bool:
        raise NotImplementedError("cloud.aws.available")

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.costs")

    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.instances")

    def utilization(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.utilization")

    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.storage")

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.user_activity")

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        raise NotImplementedError("cloud.aws.load_balancers")
