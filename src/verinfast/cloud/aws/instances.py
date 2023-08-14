import json
import os

import boto3

import cloud.aws.regions as r

regions = r.regions


def get_instances(accountId: int, path_to_output: str = "./"):
    session = boto3.Session()
    profiles = session.available_profiles
    right_session = None
    for profile in profiles:
        s2 = boto3.Session(profile_name=profile)
        sts = s2.client('sts')
        id = sts.get_caller_identity()
        if int(id['Account']) == accountId:
            right_session = s2
            break
    if right_session is None:
        return []
    my_instances = []
    for region in regions:
        try:
            client = right_session.client('ec2', region_name=region)
            paginator = client.get_paginator('describe_instances')
            page_iterator = paginator.paginate()
            for page in page_iterator:
                # print(page)
                reservations = page['Reservations']
                for reservation in reservations:
                    instances = reservation['Instances']
                    for instance in instances:
                        tags = instance['Tags']
                        name = [t['Value'] for t in tags if t['Key'] == 'Name'][0]  # noqa: E501

                        # print(instance)
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
        except:  # noqa: E722
            pass
    upload = {
                "metadata": {
                    "provider": "aws",
                    "account": str(accountId)
                },
                "data": my_instances
            }
    aws_output_file = os.path.join(
        path_to_output,
        f'aws-instances-{accountId}.json'
    )

    with open(aws_output_file, 'w') as outfile:
        outfile.write(json.dumps(upload, indent=4))
    return aws_output_file

# Test Code
# i = get_instances(436708548746)
