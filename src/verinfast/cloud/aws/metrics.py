"""AWS CloudWatch Metrics Module"""

from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Any, Optional, Union
import boto3
import botocore

from verinfast.cloud.cloud_dataclass import (
    Utilization_Datapoint as Datapoint,
    Utilization_Datum as Datum,
)


def get_instance_utilization(
    sub_id: str,
    instances: List[Dict[str, Any]],
    session: boto3.Session,
    path_to_output: str,
) -> None:
    """Get CloudWatch metrics for instances"""
    utilization_data = []

    for instance in instances:
        instance_id = instance["id"]
        metrics = _get_instance_metrics(
            instance_id, session, instance.get("region", "")
        )

        if metrics:
            utilization_data.append(
                {"id": instance_id, "metrics": [metric.dict for metric in metrics]}
            )

    _save_utilization_data(sub_id, utilization_data, path_to_output)


def _get_instance_metrics(
    instance_id: str, session: boto3.Session, region: str
) -> Optional[List[Datum]]:
    """Get CloudWatch metrics for a specific instance"""
    # Get metrics for CPU, memory, and disk
    cpu_resp = _get_metric_data(
        metric="CPUUtilization", instance_id=instance_id, session=session, region=region
    )

    mem_resp = _get_metric_data(
        metric="mem_used_percent",
        instance_id=instance_id,
        namespace="CWAgent",
        session=session,
        region=region,
    )

    hdd_resp = _get_metric_data(
        metric="disk_used_percent",
        instance_id=instance_id,
        namespace="CWAgent",
        session=session,
        region=region,
    )

    # Process metrics
    cpu_stats = _process_cpu_metrics(cpu_resp)
    mem_stats = _process_memory_metrics(mem_resp)
    hdd_stats = _process_disk_metrics(hdd_resp)

    # Combine metrics into data points
    return _combine_metrics(cpu_stats, mem_stats, hdd_stats)


def _get_metric_data(
    metric: str,
    instance_id: str,
    session: boto3.Session,
    region: str,
    namespace: str = "AWS/EC2",
    unit: str = "Percent",
) -> Optional[Dict[str, Any]]:
    """Get raw metric data from CloudWatch"""
    try:
        client = session.client("cloudwatch", region_name=region)
        return client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=datetime.utcnow() - timedelta(days=30),
            EndTime=datetime.utcnow(),
            Period=60 * 60,
            Statistics=["Average", "Maximum", "Minimum"],
            Unit=unit,
        )
    except botocore.exceptions.ClientError:
        return None


def _parse_multi(datapoint: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Datapoint:
    """Parse multiple datapoints into a single summary"""
    dp_sum: float = 0
    dp_count: int = 0
    dp_min: float = 0
    dp_max: float = 0

    my_datapoint = Datapoint()
    my_datapoint.Timestamp = datapoint["Timestamp"]

    if not isinstance(datapoint, list):
        datapoint = [datapoint]

    for entry in datapoint:
        if "Average" in entry:
            e = entry["Average"]
            dp_sum += e
            dp_count += 1
        if "Minimum" in entry:
            dp_min += entry["Minimum"]
        if "Maximum" in entry:
            dp_max += entry["Maximum"]

    dp_count = max(dp_count, 1)
    my_datapoint.Average = dp_sum / dp_count
    my_datapoint.Maximum = dp_max / dp_count
    my_datapoint.Minimum = dp_min / dp_count

    return my_datapoint


def _process_cpu_metrics(response: Optional[Dict[str, Any]]) -> List[Datapoint]:
    """Process CPU metrics"""
    if not response or "Datapoints" not in response:
        return []
    return [_parse_multi(dp) for dp in response["Datapoints"]]


def _process_memory_metrics(response: Optional[Dict[str, Any]]) -> List[Datapoint]:
    """Process memory metrics"""
    if not response or "Datapoints" not in response:
        return []
    return [Datapoint.From(dp) for dp in response["Datapoints"]]


def _process_disk_metrics(response: Optional[Dict[str, Any]]) -> List[Datapoint]:
    """Process disk metrics"""
    if not response or "Datapoints" not in response:
        return []
    return [_parse_multi(dp) for dp in response["Datapoints"]]


def _combine_metrics(
    cpu_stats: List[Datapoint], mem_stats: List[Datapoint], hdd_stats: List[Datapoint]
) -> List[Datum]:
    """Combine different metrics into unified data points"""
    data = []
    max_length = max(len(cpu_stats), len(mem_stats), len(hdd_stats))

    if max_length == 0:
        return []

    for i in range(max_length):
        datum = Datum(Timestamp=cpu_stats[i].Timestamp if i < len(cpu_stats) else None)
        datum.cpu = cpu_stats[i] if i < len(cpu_stats) else None
        datum.mem = mem_stats[i] if i < len(mem_stats) else None
        datum.hdd = hdd_stats[i] if i < len(hdd_stats) else None
        data.append(datum)

    return data


def _save_utilization_data(
    sub_id: str, utilization_data: List[Dict[str, Any]], path_to_output: str
) -> None:
    """Save utilization data to file"""
    output = {
        "metadata": {"provider": "aws", "account": str(sub_id)},
        "data": utilization_data,
    }

    output_file = os.path.join(
        path_to_output, f"aws-instances-{sub_id}-utilization.json"
    )
    with open(output_file, "w") as f:
        json.dump(output, f, indent=4)
