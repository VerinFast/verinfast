from datetime import datetime, timedelta

import json
import os

import boto3

import verinfast.cloud.aws.regions as r
from verinfast.cloud.aws.get_profile import find_profile

regions = r.regions


def getBlocks(
    sub_id: str, profile: str = None, log=None, path_to_output: str = "./", dry=False
):
    if profile is None:
        profile = find_profile(targeted_account=sub_id, log=log)

    if profile is None:
        log(msg="No matching profiles found", tag=sub_id)
        return None

    if not dry:
        right_session = boto3.Session(profile_name=profile)
        s3 = right_session.client("s3", region_name=regions[0])
        response = s3.list_buckets()
        known_buckets = {}
        for bucket in response["Buckets"]:
            bucket_name = bucket["Name"]
            resp = s3.get_bucket_location(Bucket=bucket_name)

            permissions = []
            public = False
            try:
                policy_status_resp = s3.get_bucket_policy_status(Bucket=bucket_name)
                public = policy_status_resp["PolicyStatus"]["IsPublic"]

                if "Policy" in policy_status_resp:
                    p_string = policy_status_resp["Policy"]
                    p_dict = json.loads(p_string)
                    statements = p_dict["Statement"]
                    # print(statements)
                    permissions = [json.dumps(s) for s in statements]
                    # print(s2)
            except s3.exceptions.from_code("NoSuchBucketPolicy"):
                log(msg=bucket_name, tag="No Bucket Policy for bucket")

            versioning = None
            try:
                versioning_response = s3.get_bucket_versioning(Bucket=bucket_name)
                if "Status" in versioning_response:
                    versioning = versioning_response["Status"]

            except s3.exceptions.from_code("NoSuchBucketStatus"):
                log(msg=bucket_name, tag="No Bucket Status for bucket")

            region = resp["LocationConstraint"]
            # print(region)
            if region:
                # print('Have region')
                cloudwatch = right_session.client("cloudwatch", region_name=region)
            else:
                cloudwatch = right_session.client("cloudwatch", region_name="us-east-1")

            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName="BucketSizeBytes",
                Dimensions=[
                    {"Name": "BucketName", "Value": bucket_name},
                    {"Name": "StorageType", "Value": "StandardStorage"},
                ],
                StartTime=datetime.now() - timedelta(days=2),
                EndTime=datetime.now(),
                Period=3600,
                Statistics=["Average"],
                Unit="Bytes",
            )
            if response["Datapoints"]:
                bucket_size_bytes = response["Datapoints"][-1]["Average"]
                known_buckets[bucket_name] = {
                    "name": bucket_name,
                    "size": int(bucket_size_bytes),
                    "retention": versioning,
                    "public": public,
                    "permissions": permissions,
                }
            else:
                pass
                # print(response)
            # except:
            #     pass

        my_buckets = list(known_buckets.values())
        upload = {
            "metadata": {"provider": "aws", "account": str(sub_id)},
            "data": my_buckets,
        }
    # End dry block

    aws_output_file = os.path.join(path_to_output, f"aws-storage-{sub_id}.json")

    if not dry:
        with open(aws_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))

    return aws_output_file


# Test Code
# getBlocks(sub_id='436708548746')
