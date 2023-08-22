from datetime import datetime, timedelta
import json
import os
from typing import List

import boto3

import verinfast.cloud.aws.regions as r
from verinfast.cloud.cloud_dataclass import \
    Utilization_Datapoint as Datapoint,  \
    Utilization_Datum as Datum

regions = r.regions


def get_metric_for_instance(
            metric: str,
            instance_id: str,
            namespace: str = 'AWS/EC2',
            unit: str = 'Percent'
        ):
    client = boto3.client('cloudwatch')
    response = client.get_metric_statistics(
        Namespace=namespace,
        MetricName=metric,
        Dimensions=[
            {
                'Name': 'InstanceId',
                'Value': instance_id
            },
        ],
        StartTime=datetime.today() - timedelta(days=30),
        EndTime=datetime.today(),
        Period=60*60,
        Statistics=[
            'Average',
            'Maximum',
            'Minimum'
        ],
        Unit=unit
    )
    return response


def parse_multi(datapoint: dict) -> Datapoint:
    dp_sum: float = 0
    dp_count: int = 0
    dp_min: float = 0
    dp_max: float = 0

    my_datapoint = Datapoint()
    for entry in datapoint:
        if 'Average' in entry:
            e = entry['Average']
            dp_sum += e
            dp_count += 1
        if 'Minimum' in entry:
            dp_min += entry['Minimum']
        if 'Maximum' in entry:
            dp_max += entry['Maximum']

    dp_count = max(dp_count, 1)
    my_datapoint.Average = dp_sum / dp_count
    my_datapoint.Maximum = dp_max / dp_count
    my_datapoint.Minimum = dp_min / dp_count

    my_datapoint.Timestamp = datapoint['Timestamp']

    return my_datapoint


def get_instance_utilization(instance_id: str) -> List[Datum]:
    cpu_resp = get_metric_for_instance(
            metric='CPUUtilization',
            instance_id=instance_id
        )
    try:
        mem_resp = get_metric_for_instance(
                metric='mem_used_percent',
                instance_id=instance_id,
                namespace='CWAgent'
            )

        hdd_resp = get_metric_for_instance(
                metric='disk_used_percent',
                instance_id=instance_id,
                namespace='CWAgent'
            )
    except Exception:
        pass

    cpu_stats = []
    mem_stats = []
    hdd_stats = []
    print(cpu_resp)
    # each instance may have more than 1 CPU
    for datapoint in cpu_resp['Datapoints']:
        summary = parse_multi(datapoint)
        cpu_stats.append(summary)

    # memory and disk are not collected by default
    try:
        # each instance may have more than one disk
        if "Datapoints" in hdd_resp:
            for datapoint in hdd_resp["Datapoints"]:
                summary = parse_multi(datapoint)
                hdd_stats.append(summary)
        # memory
        if "Datapoints" in mem_resp:
            mem_stats = [Datapoint.From(i) for i in mem_resp["Datapoints"]]
    except Exception:
        pass
    data = []
    m = max(len(cpu_stats), len(mem_stats), len(hdd_stats))
    if m == 0:
        return []
    else:
        for i in range(m):
            datum = Datum()
            if i <= len(cpu_stats):
                datum.cpu = cpu_stats[i]
            else:
                datum.cpu = None
            if i <= len(mem_stats):
                datum.mem = mem_stats[i]
            else:
                datum.mem = None
            if i <= len(hdd_stats):
                datum.hdd = hdd_stats[i]
            else:
                datum.hdd = None

            data.append(datum)
    return data


def get_instances(sub_id: int, path_to_output: str = "./") -> str | None:
    session = boto3.Session()
    profiles = session.available_profiles
    right_session = None
    for profile in profiles:
        s2 = boto3.Session(profile_name=profile)
        sts = s2.client('sts')
        id = sts.get_caller_identity()
        if int(id['Account']) == sub_id:
            right_session = s2
            break
    if right_session is None:
        return None
    my_instances = []
    metrics = []
    for region in regions:
        try:
            client = right_session.client('ec2', region_name=region)
            paginator = client.get_paginator('describe_instances')
            page_iterator = paginator.paginate()
            for page in page_iterator:
                reservations = page['Reservations']
                for reservation in reservations:
                    instances = reservation['Instances']
                    for instance in instances:
                        tags = instance['Tags']
                        name = [t['Value'] for t in tags if t['Key'] == 'Name'][0]  # noqa: E501
                        m = get_instance_utilization(
                            instance_id=instance["InstanceId"]
                        )
                        d = {
                                "id": instance["InstanceId"],
                                "metrics": [metric.dict for metric in m]
                            }
                        metrics.append(d)
                        result = {
                            "id": instance["InstanceId"],
                            "name": name,
                            "state": instance["State"]["Name"],
                            "type": instance['InstanceType'],
                            "zone": instance['Placement']['AvailabilityZone'],
                            "region": instance['Placement']['AvailabilityZone'][0:-1],  # noqa: E501
                            "subnet": instance['SubnetId'],
                            "architecture": instance['Architecture'],
                            "vpc": instance['VpcId'],
                        }
                        if "PublicIpAddress" in result:
                            result["publicIp"] = instance['PublicIpAddress']
                        else:
                            result["publicIp"] = 'n/a'
                        ni = instance["NetworkInterfaces"]
                        for interface in ni:
                            if 'Association' in interface:
                                if 'PublicIp' in interface['Association']:
                                    result["publicIp"] = interface['Association']['PublicIp']  # noqa: E501
                        my_instances.append(result)
        except Exception:  # noqa: E722
            pass
    upload = {
                "metadata": {
                    "provider": "aws",
                    "account": str(sub_id)
                },
                "data": my_instances
            }
    aws_output_file = os.path.join(
        path_to_output,
        f'aws-instances-{sub_id}.json'
    )

    with open(aws_output_file, 'w') as outfile:
        outfile.write(json.dumps(upload, indent=4))

    upload['data'] = metrics
    with open(aws_output_file[:-5]+"-utilization.json", "w") as outfile2:
        outfile2.write(json.dumps(upload, indent=4))

    return aws_output_file

# Test Code
# i = get_instances(436708548746)
