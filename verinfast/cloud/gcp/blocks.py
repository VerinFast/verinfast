import json
import time

from google.cloud.monitoring_v3 import query, QueryServiceClient, MetricServiceClient, TimeInterval, ListTimeSeriesRequest
from google.cloud import storage

def getBlocks(sub_id:str):
    # Instantiates a client
    storage_client = storage.Client(project=sub_id)

    # List all the buckets available
    client = MetricServiceClient()
    # for bucket in storage_client.list_buckets():
        # print(bucket)
        # print(bucket.name)

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
            "filter": f'metric.type = "storage.googleapis.com/storage/total_bytes"',
            "interval": interval,
            "view": ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )
    my_buckets = []
    for result in results:
        if result.resource and result.resource.labels:
            bn = result.resource.labels["bucket_name"]
            size = result.points[-1].value.double_value 
            bucket = storage_client.get_bucket(bucket_or_name=bn)
            rp = bucket.retention_period
            my_bucket = {
                "name": bn,
                "size": size,
                "retention": rp,
                "public": False
            }
            configuration = bucket.iam_configuration
            uniformEnabled = configuration['uniformBucketLevelAccess']['enabled']
            iam = bucket.get_iam_policy()
            permissions = []
            blobs = bucket.list_blobs()
            for bl in blobs:
                i = bl.get_iam_policy()
                for bin in i.bindings:
                    print(bin)
            for b in iam.bindings:
                p = {"permission": b["role"], "roles": list(b["members"])}
                permissions.append(p)
                if "allUsers" in b["members"]:
                    my_bucket["public"] = True
            my_bucket["permissions"] = permissions
            my_buckets.append(my_bucket)
    return my_buckets
    
print(json.dumps(getBlocks(sub_id="startupos-328814"), indent=4))
