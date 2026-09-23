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
from verinfast2.models import ArtifactResult, CloudAccount


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

    Raises:
        NotImplementedError: no provider is ported yet.
    """
    raise NotImplementedError("cloud.base.provider_for")
