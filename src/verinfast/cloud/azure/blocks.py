import datetime
import json
import os

from azure.identity import DefaultAzureCredential
from azure.monitor.query import MetricsQueryClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.resource import ResourceManagementClient


def getBlocks(sub_id: str, path_to_output: str = "./", dry=False):
    if not dry:
        credential = DefaultAzureCredential()
        client = MetricsQueryClient(credential)
        resource_client = ResourceManagementClient(credential, subscription_id=sub_id)

        group_list = resource_client.resource_groups.list()
        storage_client = StorageManagementClient(credential, subscription_id=sub_id)

        known_buckets = {}
        for group in group_list:
            accounts = storage_client.storage_accounts.list_by_resource_group(
                resource_group_name=group.name
            )

            for account in accounts:
                containers = storage_client.blob_containers.list(
                    resource_group_name=group.name, account_name=account.name
                )

                d = datetime.timedelta(
                    days=1,
                    seconds=0,
                    microseconds=0,
                    milliseconds=0,
                    minutes=0,
                    hours=0,
                    weeks=0,
                )

                o = client.query_resource(
                    resource_uri=account.id, metric_names=["UsedCapacity"], timespan=d
                )

                bytes = o.metrics[0].timeseries[0].data[0].average
                print(bytes)
                known_buckets[account.name] = {
                    "name": account.name,
                    "size": bytes,
                    "retention": None,
                    "public": False,
                    "permissions": [],
                }
                for c in containers:
                    if c.public_access:
                        known_buckets[account.name]["public"] = True
        my_buckets = list(known_buckets.values())
        upload = {
            "metadata": {"provider": "azure", "account": str(sub_id)},
            "data": my_buckets,
        }
    # End dry block
    azure_output_file = os.path.join(path_to_output, f"az-storage-{sub_id}.json")
    if not dry:
        with open(azure_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))
    return azure_output_file


# Test Code
# getBlocks(sub_id="80dc7a6b-df94-44be-a235-7e7ade335a3c")
