import json
import os
import time

from google.cloud.monitoring_v3 import MetricServiceClient, TimeInterval, ListTimeSeriesRequest  # noqa: E501
from google.cloud import storage


def getBlocks(sub_id: str, path_to_output: str = "./"):
    # Instantiates a client
    storage_client = storage.Client(project=sub_id)

    # List all the buckets available
    client = MetricServiceClient()
    # for bucket in storage_client.list_buckets():
    #     print(bucket)
    #     print(bucket.name)

    now = time.time()
    seconds = int(now)
    nanos = int((now - seconds) * 10**9)
    interval = TimeInterval(
        {
            "end_time": {"seconds": seconds, "nanos": nanos},
            "start_time": {"seconds": (seconds - 300), "nanos": nanos},
        }
    )

    results = client.list_time_series(
        request={
            "name": f"projects/{sub_id}",
            "filter": 'metric.type = "storage.googleapis.com/storage/total_bytes"',  # noqa: E501
            "interval": interval,
            "view": ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )
    my_buckets = []
    known_buckets = {}
    all_buckets = storage_client.list_buckets()
    for bucket in all_buckets:
        rp = bucket.retention_period
        known_buckets[bucket.name] = {
            "name": bucket.name,
            "size": 0,
            "retention": rp,
            "public": False
        }
        iam = bucket.get_iam_policy()
        permissions = []
        for b in iam.bindings:
            p = {"permission": b["role"], "roles": list(b["members"])}
            permissions.append(json.dumps(p))
            if "allUsers" in b["members"]:
                known_buckets[bucket.name]["public"] = True
        known_buckets[bucket.name]["permissions"] = permissions

    for result in results:
        if result.resource and result.resource.labels:
            bn = result.resource.labels["bucket_name"]
            size = result.points[-1].value.double_value
            if bn in known_buckets:
                known_buckets[bn]["size"] = size
    my_buckets = list(known_buckets.values())
    upload = {
                "metadata": {
                    "provider": "gcp",
                    "account": str(sub_id)
                },
                "data": my_buckets
            }
    gcp_output_file = os.path.join(
        path_to_output,
        f'gcp-storage-{sub_id}.json'
    )
    with open(gcp_output_file, 'w') as outfile:
        outfile.write(json.dumps(upload, indent=4))
    return gcp_output_file

# Test Code
# getBlocks(sub_id="startupos-328814")
