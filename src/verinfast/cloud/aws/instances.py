from datetime import datetime, timedelta
import json
import os
from typing import List, Union

import boto3
import botocore

import verinfast.cloud.aws.regions as r
from verinfast.cloud.aws.get_profile import find_profile
from verinfast.cloud.cloud_dataclass import (
    Utilization_Datapoint as Datapoint,
    Utilization_Datum as Datum,
)

regions = r.regions


def get_metric_for_instance(
    metric: str,
    instance_id: str,
    session,
    region: str,
    namespace: str = "AWS/EC2",
    unit: str = "Percent",
):
    try:
        client = session.client("cloudwatch", region_name=region)
        response = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=[
                {"Name": "InstanceId", "Value": instance_id},
            ],
            StartTime=datetime.utcnow() - timedelta(days=30),
            EndTime=datetime.utcnow(),
            Period=60 * 60,
            Statistics=["Average", "Maximum", "Minimum"],
            Unit=unit,
        )
        return response
    except botocore.exceptions.ClientError:
        pass


def parse_multi(datapoint: Union[dict, List[dict]]) -> Datapoint:
    dp_sum: float = 0
    dp_count: int = 0
    dp_min: float = 0
    dp_max: float = 0

    my_datapoint = Datapoint()
    my_datapoint.Timestamp = datapoint["Timestamp"]
    if type(datapoint) is not list:
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


def get_instance_utilization(instance_id: str, session, region: str) -> List[Datum]:
    cpu_resp = get_metric_for_instance(
        metric="CPUUtilization", instance_id=instance_id, session=session, region=region
    )
    mem_resp = get_metric_for_instance(
        metric="mem_used_percent",
        instance_id=instance_id,
        namespace="CWAgent",
        session=session,
        region=region,
    )

    hdd_resp = get_metric_for_instance(
        metric="disk_used_percent",
        instance_id=instance_id,
        namespace="CWAgent",
        session=session,
        region=region,
    )

    cpu_stats: List[Datapoint] = []
    mem_stats: List[Datapoint] = []
    hdd_stats: List[Datapoint] = []

    # each instance may have more than 1 CPU
    for datapoint in cpu_resp["Datapoints"]:
        summary = parse_multi(datapoint)
        cpu_stats.append(summary)

    # memory and disk are not collected by default
    # each instance may have more than one disk
    if "Datapoints" in hdd_resp:
        for datapoint in hdd_resp["Datapoints"]:
            summary = parse_multi(datapoint)
            hdd_stats.append(summary)
    # memory
    if "Datapoints" in mem_resp:
        mem_stats = [Datapoint.From(i) for i in mem_resp["Datapoints"]]

    data = []
    m = max(len(cpu_stats), len(mem_stats), len(hdd_stats))
    if m == 0:
        return []
    else:
        for i in range(m):
            datum = Datum(Timestamp=cpu_stats[i].Timestamp)
            if i < len(cpu_stats):
                datum.cpu = cpu_stats[i]
            else:
                datum.cpu = None
            if i < len(mem_stats):
                datum.mem = mem_stats[i]
            else:
                datum.mem = None
            if i < len(hdd_stats):
                datum.hdd = hdd_stats[i]
            else:
                datum.hdd = None
            data.append(datum)
    return data


def get_instances(
    sub_id: str, profile: str = None, log=None, path_to_output: str = "./", dry=False
):
    if profile is None:
        profile = find_profile(targeted_account=sub_id, log=log)

    if profile is None:
        log(msg="No matching profiles found", tag=sub_id)
        return None

    if not dry:
        right_session = boto3.Session(profile_name=profile)
        my_instances = []
        metrics = []
        for region in regions:
            try:
                client = right_session.client("ec2", region_name=region)
                paginator = client.get_paginator("describe_instances")
                page_iterator = paginator.paginate()
                for page in page_iterator:
                    reservations = page["Reservations"]
                    for reservation in reservations:
                        instances = reservation["Instances"]
                        for instance in instances:
                            tags = instance.get("Tags")
                            if tags is None:
                                name = instance["InstanceId"]
                            else:
                                tags_with_name = [
                                    t["Value"] for t in tags if t["Key"] == "Name"
                                ]
                                if not tags_with_name:
                                    name = instance["InstanceId"]
                                else:
                                    name = tags_with_name[0]
                            m = get_instance_utilization(
                                instance_id=instance["InstanceId"],
                                session=right_session,
                                region=region,
                            )
                            d = {
                                "id": instance["InstanceId"],
                                "metrics": [metric.dict for metric in m],
                            }
                            metrics.append(d)
                            region = None
                            subnet_id = None
                            zone = None
                            if "SubnetId" in instance:
                                subnet_id = instance["SubnetId"]
                            if "Placement" in instance:
                                placement = instance["Placement"]
                                if "AvailabilityZone" in placement:
                                    zone = placement["AvailabilityZone"]
                                    region = zone[0:-1]
                            try:
                                result = {
                                    "id": instance["InstanceId"],
                                    "name": name or "n/a",
                                    "state": instance["State"]["Name"],
                                    "type": instance["InstanceType"],
                                    "zone": zone or "n/a",
                                    "region": region or "n/a",
                                    "subnet": (subnet_id or "n/a"),
                                    "architecture": instance["Architecture"],
                                }
                            except Exception as e:
                                if log:
                                    log(tag="AWS Get Instance Error", msg=str(e))
                                continue
                            if "VpcId" in instance:
                                result["vpc"] = instance["VpcId"]
                            else:
                                result["vpc"] = "n/a"
                            if "PublicIpAddress" in instance:
                                result["publicIp"] = instance["PublicIpAddress"]
                            else:
                                result["publicIp"] = "n/a"
                            if "NetworkInterfaces" in instance:
                                ni = instance["NetworkInterfaces"]
                                for interface in ni:
                                    if "Association" in interface:
                                        association = interface["Association"]
                                        if "PublicIp" in association:
                                            public_ip = association["PublicIp"]
                                            result["publicIp"] = public_ip
                            my_instances.append(result)
            except Exception as e:
                if log:
                    log(tag="AWS Get Instance Error - Region", msg=str(e))
                pass

        upload = {
            "metadata": {"provider": "aws", "account": str(sub_id)},
            "data": my_instances,
        }
    # End dry check

    aws_output_file = os.path.join(path_to_output, f"aws-instances-{sub_id}.json")

    if not dry:
        with open(aws_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))
        upload["data"] = metrics
        with open(aws_output_file[:-5] + "-utilization.json", "w") as outfile2:
            outfile2.write(json.dumps(upload, indent=4))

    return aws_output_file
