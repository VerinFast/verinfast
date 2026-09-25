"""Per-resource Azure metric queries on top of ``azure-monitor-querymetrics``.

``azure-monitor-query`` 2.0.0 removed ``MetricsQueryClient``: the metrics half
of that SDK now ships separately as ``azure-monitor-querymetrics``. Its
``MetricsClient`` differs from the 1.x client in three ways that reach the
collectors in this package:

* It is built against a *regional* data-plane endpoint
  (``https://<region>.metrics.monitor.azure.com``) instead of the single
  ``https://management.azure.com`` control-plane host, so one client can no
  longer serve a whole subscription -- each resource has to be queried through
  the endpoint for its own region.
* ``query_resources`` is a batch call: it takes ``resource_ids`` and returns a
  *list* of results, where ``query_resource`` took one ``resource_uri`` and
  returned one result.
* ``metric_namespace`` is required, where it used to be optional.

``RegionalMetricsClient`` absorbs all three, so callers keep querying one
resource at a time and keep walking a single ``MetricsQueryResult`` exactly as
they did under 1.x. The JSON the collectors emit is therefore unchanged.
"""

import datetime
from typing import Dict, Optional, Sequence, Union

from azure.core.credentials import TokenCredential
from azure.monitor.querymetrics import (
    MetricAggregationType,
    MetricsClient,
    MetricsQueryResult,
)

# Resources with no region of their own are queried through the global endpoint.
GLOBAL_REGION = "global"

Timespan = Union[
    datetime.timedelta,
    "tuple[datetime.datetime, datetime.timedelta]",
    "tuple[datetime.datetime, datetime.datetime]",
]


def normalize_region(region: Optional[str]) -> str:
    """Reduce an Azure location to the spelling used in metrics endpoints.

    The management SDKs report locations inconsistently -- ``eastus`` from some
    operations, ``East US`` from others -- while the endpoint host wants the
    compact lowercase form.
    """
    if not region or not region.strip():
        return GLOBAL_REGION
    return region.replace(" ", "").lower()


def metrics_endpoint(region: Optional[str]) -> str:
    """The regional metrics data-plane endpoint for ``region``."""
    return f"https://{normalize_region(region)}.metrics.monitor.azure.com"


class RegionalMetricsClient:
    """Queries one resource at a time, through its own region's endpoint.

    A ``MetricsClient`` is bound to a single region, so one is created per
    region encountered and reused for every later resource in that region.
    """

    def __init__(self, credential: TokenCredential) -> None:
        self._credential = credential
        self._clients: Dict[str, MetricsClient] = {}

    def client_for(self, region: Optional[str]) -> MetricsClient:
        """The cached ``MetricsClient`` for ``region``, creating it if needed."""
        normalized = normalize_region(region)
        if normalized not in self._clients:
            self._clients[normalized] = MetricsClient(
                metrics_endpoint(normalized), self._credential
            )
        return self._clients[normalized]

    def query_resource(
        self,
        *,
        resource_id: str,
        region: Optional[str],
        metric_namespace: str,
        metric_names: Sequence[str],
        timespan: Optional[Timespan] = None,
        granularity: Optional[datetime.timedelta] = None,
        aggregations: Optional[Sequence[Union[MetricAggregationType, str]]] = None,
    ) -> MetricsQueryResult:
        """Query metrics for a single resource.

        Mirrors the 1.x ``MetricsQueryClient.query_resource``: one resource in,
        one ``MetricsQueryResult`` out.

        :raises ValueError: if the service returns no result for the resource.
            Callers see this the same way they saw an empty ``metrics`` list
            under 1.x -- as a failed lookup for this one resource.
        """
        results = self.client_for(region).query_resources(
            resource_ids=[resource_id],
            metric_namespace=metric_namespace,
            metric_names=list(metric_names),
            timespan=timespan,
            granularity=granularity,
            aggregations=aggregations,
        )
        if not results:
            raise ValueError(f"No metrics returned for resource {resource_id}")
        return results[0]

    def close(self) -> None:
        """Close every client this instance opened."""
        for client in self._clients.values():
            client.close()
        self._clients.clear()

    def __enter__(self) -> "RegionalMetricsClient":
        return self

    def __exit__(self, *exc_details) -> None:
        self.close()
