"""One interface for the three cloud providers.

v1 dispatched with a 150-line ``if provider == "aws": ... if == "azure": ...``
chain inside ``Agent.scanCloud``, wrapped in a single bare ``except:`` that
made a credential error and a parse error indistinguishable (`N7`, `N10`).

Here a provider implements six methods and the orchestrator does not care
which one it is holding. Adding a provider, or an artifact, is additive.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, CloudAccount, Outcome


@runtime_checkable
class CloudProvider(Protocol):
    """Collect cost and inventory data for one account.

    Every method returns a result rather than raising, so one artifact
    failing does not lose the other five (`F19`).
    """

    #: ``"aws"``, ``"azure"`` or ``"gcp"``.
    name: str

    def available(self, ctx: ScanContext) -> bool:
        """Whether credentials and tooling for this provider are present."""
        ...

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult: ...
    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult: ...
    def utilization(
        self, ctx: ScanContext, account: CloudAccount
    ) -> ArtifactResult: ...
    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult: ...

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        """Console/API sign-in and admin activity.

        New in v2. ATD v3 has shipped the ingest route, models, migration and
        a widget waiting on it; nothing populates the table until this exists
        (`F8`).
        """
        ...

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        """Load-balancer inventory. Also new in v2, also awaited by ATD."""
        ...


def provider_for(name: str) -> CloudProvider:
    """The provider implementation for ``aws``/``azure``/``gcp``.

    Imported lazily, one provider at a time: the SDKs are moving behind
    extras, and a scan of an AWS account must not need ``azure-mgmt-*``
    installed to get as far as finding out it doesn't need them.

    Raises:
        KeyError: no provider by that name. A typo in the config is a
            configuration error, not an artifact that silently collects
            nothing.
    """
    if name == "aws":
        from verinfast2.cloud.aws import AwsProvider

        return AwsProvider()
    if name == "azure":
        from verinfast2.cloud.azure import AzureProvider

        return AzureProvider()
    if name == "gcp":
        from verinfast2.cloud.gcp import GcpProvider

        return GcpProvider()
    raise KeyError(name)


# -- Result helpers ------------------------------------------------------------
# Every provider builds the same three shapes, and `F19` only holds if a
# failure is *returned*. Defined here so the three providers cannot drift into
# three spellings of "this didn't run" -- and so `_check_coverage`'s rule holds
# at this layer too: "collected nothing" and "never ran" must never look alike
# (`F18`). An OK result with `rows == []` is the first; SKIPPED and FAILED are
# the second, and both carry a reason.


def ok(artifact: Artifact, account: CloudAccount, rows: list) -> ArtifactResult:
    """Rows collected. An empty list is a real answer: the account has none."""
    return ArtifactResult(
        artifact=artifact, target=account.account, outcome=Outcome.OK, data=rows
    )


def skipped(artifact: Artifact, account: CloudAccount, why: str) -> ArtifactResult:
    """Deliberately not collected -- no credentials, not ported, switched off."""
    return ArtifactResult(
        artifact=artifact,
        target=account.account,
        outcome=Outcome.SKIPPED,
        error=why,
    )


def failed(artifact: Artifact, account: CloudAccount, error: str) -> ArtifactResult:
    """Tried and could not. Distinct from SKIPPED on purpose (`N10`)."""
    return ArtifactResult(
        artifact=artifact,
        target=account.account,
        outcome=Outcome.FAILED,
        error=error,
    )
