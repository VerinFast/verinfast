"""AWS Instance Management Module"""
import json
import os
from typing import Optional, List, Dict, Any
import boto3

from .instance_utils import process_instance_data
from .metrics import get_instance_utilization
from .get_profile import find_profile
from . import regions


def get_instances(
    sub_id: str,
    profile: str = None,
    log=None,
    path_to_output: str = "./",
    dry: bool = False
) -> Optional[str]:
    """Get AWS EC2 instance information"""
    if dry:
        return None

    # Find AWS profile
    if profile is None:
        profile = find_profile(targeted_account=sub_id, log=log)

    if profile is None:
        if log:
            log(msg="No matching profiles found", tag=sub_id)
        return None

    # Initialize session and collect instance data
    session = boto3.Session(profile_name=profile)
    instances_data = _collect_instances_data(session, log)

    if not instances_data:
        return None

    # Save instance data
    output_file = os.path.join(path_to_output, f'aws-instances-{sub_id}.json')
    _save_instance_data(sub_id, instances_data, output_file)

    # Get and save utilization data
    get_instance_utilization(sub_id, instances_data, session, path_to_output)

    return output_file


def _collect_instances_data(
    session: boto3.Session,
    log
) -> List[Dict[str, Any]]:
    """Collect instance data from all regions"""
    instances = []

    for region in regions.regions:
        try:
            client = session.client('ec2', region_name=region)
            paginator = client.get_paginator('describe_instances')

            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        try:
                            instance_info = process_instance_data(instance, region)
                            instances.append(instance_info)
                        except Exception as e:
                            if log:
                                log(tag="AWS Get Instance Error", msg=str(e))
        except Exception as e:
            if log:
                log(tag="AWS Get Instance Error - Region", msg=str(e))
            continue

    return instances


def _save_instance_data(
    sub_id: str,
    instances: List[Dict[str, Any]],
    output_file: str
) -> None:
    """Save instance data to file"""
    output = {
        "metadata": {
            "provider": "aws",
            "account": str(sub_id)
        },
        "data": instances
    }

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=4)
