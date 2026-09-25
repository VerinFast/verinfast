"""Cover the port from azure-monitor-query 1.x metrics to azure-monitor-querymetrics.

``azure-monitor-query`` 2.0.0 dropped ``MetricsQueryClient``, so the Azure
collectors now reach the metrics service through ``azure-monitor-querymetrics``.
That client is regional, batch-oriented and requires a metric namespace, none of
which may show up in the JSON the collectors emit -- these tests pin both the
wire parameters going out and the shape coming back.
"""

import datetime
from unittest import mock

from azure.monitor.querymetrics import MetricsClient
from azure.monitor.querymetrics._models import MetricsQueryResult

import verinfast.cloud.azure.blocks as blocks
import verinfast.cloud.azure.instances as instances
from verinfast.cloud.azure.metrics import (
    RegionalMetricsClient,
    metrics_endpoint,
    normalize_region,
)

VM_ID = (
    "/subscriptions/sub-abc/resourceGroups/rg"
    "/providers/Microsoft.Compute/virtualMachines/vm-1"
)
ACCOUNT_ID = (
    "/subscriptions/sub-abc/resourceGroups/rg"
    "/providers/Microsoft.Storage/storageAccounts/acct1"
)

# The raw service payload, in the shape both SDK generations deserialize. The
# third window is one the service reported with no samples at all.
CPU_PAYLOAD = {
    "cost": 0,
    "timespan": "2026-08-26T00:00:00Z/2026-09-25T00:00:00Z",
    "interval": "PT1H",
    "namespace": "Microsoft.Compute/virtualMachines",
    "resourceregion": "eastus",
    "value": [
        {
            "id": f"{VM_ID}/providers/Microsoft.Insights/metrics/Percentage CPU",
            "type": "Microsoft.Insights/metrics",
            "name": {"value": "Percentage CPU", "localizedValue": "Percentage CPU"},
            "displayDescription": "The percentage of allocated compute units in use.",
            "unit": "Percent",
            "timeseries": [
                {
                    "metadatavalues": [],
                    "data": [
                        {
                            "timeStamp": "2026-08-26T00:00:00Z",
                            "minimum": 1.25,
                            "average": 12.5,
                            "maximum": 71.0,
                        },
                        {
                            "timeStamp": "2026-08-26T01:00:00Z",
                            "minimum": 0.0,
                            "average": 3.125,
                            "maximum": 9.5,
                        },
                        {"timeStamp": "2026-08-26T02:00:00Z"},
                    ],
                }
            ],
        }
    ],
}

CAPACITY_PAYLOAD = {
    "cost": 0,
    "timespan": "2026-09-24T00:00:00Z/2026-09-25T00:00:00Z",
    "interval": "PT1H",
    "namespace": "Microsoft.Storage/storageAccounts",
    "resourceregion": "westeurope",
    "value": [
        {
            "id": f"{ACCOUNT_ID}/providers/Microsoft.Insights/metrics/UsedCapacity",
            "type": "Microsoft.Insights/metrics",
            "name": {"value": "UsedCapacity", "localizedValue": "Used capacity"},
            "displayDescription": "The amount of storage used by the storage account.",
            "unit": "Bytes",
            "timeseries": [
                {
                    "metadatavalues": [],
                    "data": [
                        {"timeStamp": "2026-09-24T00:00:00Z", "average": 1234567890.0}
                    ],
                }
            ],
        }
    ],
}


def _result(payload):
    return MetricsQueryResult._from_generated(dict(payload))


def _capture(region, payload, call):
    """Run ``call`` against a client whose generated batch op is stubbed.

    Returns the endpoint the client was built against and the keyword arguments
    that reached the service.
    """
    client = RegionalMetricsClient(credential=mock.MagicMock())
    inner = client.client_for(region)
    with mock.patch.object(
        MetricsClient, "_query_resources", return_value={"values": [payload]}
    ) as op:
        call(client)
    return inner._endpoint, op.call_args.kwargs


def _timespan_width(kwargs):
    started = datetime.datetime.fromisoformat(
        kwargs["start_time"].replace("Z", "+00:00")
    )
    ended = datetime.datetime.fromisoformat(kwargs["end_time"].replace("Z", "+00:00"))
    return ended - started


def test_normalize_region_handles_both_spellings():
    # The management SDKs report locations as "eastus" from some operations and
    # "East US" from others; the endpoint host wants the compact form.
    assert normalize_region("eastus") == "eastus"
    assert normalize_region("East US") == "eastus"
    assert normalize_region("West Europe") == "westeurope"


def test_normalize_region_falls_back_to_global():
    for missing in (None, "", "   "):
        assert normalize_region(missing) == "global"


def test_metrics_endpoint_is_regional():
    assert metrics_endpoint("East US") == "https://eastus.metrics.monitor.azure.com"
    assert metrics_endpoint(None) == "https://global.metrics.monitor.azure.com"


def test_one_client_per_region_is_reused():
    client = RegionalMetricsClient(credential=mock.MagicMock())
    first = client.client_for("eastus")
    assert client.client_for("East US") is first
    assert client.client_for("westus2") is not first
    assert set(client._clients) == {"eastus", "westus2"}


def test_instance_query_reaches_the_service_unchanged():
    endpoint, kwargs = _capture(
        "eastus",
        CPU_PAYLOAD,
        lambda c: instances.get_metrics_for_instance(
            metrics_client=c,
            instance_id=VM_ID,
            instance_name="vm-1",
            region="eastus",
        ),
    )
    assert endpoint == "https://eastus.metrics.monitor.azure.com"
    assert kwargs["subscription_id"] == "sub-abc"
    assert kwargs["batch_request"] == {"resourceids": [VM_ID]}
    assert kwargs["metric_namespace"] == "Microsoft.Compute/virtualMachines"
    assert kwargs["metric_names"] == ["Percentage CPU"]
    assert kwargs["aggregation"] == "Minimum,Average,Maximum"
    # The hourly window now actually reaches the service: under 1.x it was
    # passed as `interval`, which collided with the parameter it was meant to
    # set and raised TypeError before any request went out.
    assert kwargs["interval"] == "PT1H"
    assert _timespan_width(kwargs) == datetime.timedelta(days=30)


def test_instance_metrics_json_is_unchanged():
    client = RegionalMetricsClient(credential=mock.MagicMock())
    inner = mock.MagicMock()
    inner.query_resources.return_value = [_result(CPU_PAYLOAD)]
    client._clients["eastus"] = inner

    data = instances.get_metrics_for_instance(
        metrics_client=client,
        instance_id=VM_ID,
        instance_name="vm-1",
        region="eastus",
    )

    assert [datum.dict for datum in data] == [
        {
            "timestamp": 1787702400.0,
            "cpu": {"minimum": 1.25, "average": 12.5, "maximum": 71.0},
        },
        {
            "timestamp": 1787706000.0,
            "cpu": {"minimum": 0.0, "average": 3.125, "maximum": 9.5},
        },
        # A window with no samples still emits a datapoint with a null body.
        {"timestamp": 1787709600.0, "cpu": None},
    ]


def test_storage_query_reaches_the_service_unchanged():
    endpoint, kwargs = _capture(
        "West Europe",
        CAPACITY_PAYLOAD,
        lambda c: c.query_resource(
            resource_id=ACCOUNT_ID,
            region="West Europe",
            metric_namespace=blocks.metric_namespace,
            metric_names=["UsedCapacity"],
            timespan=datetime.timedelta(days=1),
        ),
    )
    assert endpoint == "https://westeurope.metrics.monitor.azure.com"
    assert kwargs["metric_namespace"] == "Microsoft.Storage/storageAccounts"
    assert kwargs["metric_names"] == ["UsedCapacity"]
    # blocks.py asked for neither, and still leaves both to the service default.
    assert kwargs["aggregation"] is None
    assert kwargs["interval"] is None
    assert _timespan_width(kwargs) == datetime.timedelta(days=1)


def test_storage_size_is_read_from_the_same_place():
    result = _result(CAPACITY_PAYLOAD)
    assert result.metrics[0].timeseries[0].data[0].average == 1234567890.0
    assert result.metrics["UsedCapacity"].unit == "Bytes"


def test_empty_batch_response_raises():
    client = RegionalMetricsClient(credential=mock.MagicMock())
    client.client_for("eastus")
    with mock.patch.object(
        MetricsClient, "_query_resources", return_value={"values": []}
    ):
        try:
            client.query_resource(
                resource_id=VM_ID,
                region="eastus",
                metric_namespace="Microsoft.Compute/virtualMachines",
                metric_names=["Percentage CPU"],
            )
        except ValueError as exc:
            assert VM_ID in str(exc)
        else:
            raise AssertionError("expected ValueError for an empty batch response")


def test_instance_collector_survives_a_failed_lookup():
    # A resource the service returns nothing for must leave the collector
    # reporting no datapoints, exactly as an empty result did under 1.x.
    client = RegionalMetricsClient(credential=mock.MagicMock())
    client.client_for("eastus")
    with mock.patch.object(
        MetricsClient, "_query_resources", return_value={"values": []}
    ):
        assert (
            instances.get_metrics_for_instance(
                metrics_client=client,
                instance_id=VM_ID,
                instance_name="vm-1",
                region="eastus",
            )
            == []
        )


def test_close_releases_every_regional_client():
    client = RegionalMetricsClient(credential=mock.MagicMock())
    opened = [client.client_for("eastus"), client.client_for("westus2")]
    with mock.patch.object(MetricsClient, "close") as closed:
        client.close()
    assert closed.call_count == len(opened)
    assert client._clients == {}
