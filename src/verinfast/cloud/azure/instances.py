import datetime
import json
import os
from typing import List

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.monitor.query import MetricsQueryClient, MetricAggregationType


from verinfast.cloud.cloud_dataclass import \
    Utilization_Datapoint as Datapoint,  \
    Utilization_Datum as Datum


metric_name = "Percentage CPU"
d = datetime.timedelta(
                days=30,
                seconds=0,
                microseconds=0,
                milliseconds=0,
                minutes=0,
                hours=0,
                weeks=0
            )

metric_identifiers = {"cpu": metric_name}
aggregations = [
    MetricAggregationType.MINIMUM,
    MetricAggregationType.AVERAGE,
    MetricAggregationType.MAXIMUM
]


def get_metrics_for_instance(
        metrics_client: MetricsQueryClient,
        instance_id: str,
        instance_name: str
        ) -> List[Datum]:
    print("Get Metrics for Instance")
    data = []
    try:
        o = metrics_client.query_resource(
            resource_uri=instance_id,
            interval=datetime.timedelta(hours=1),
            aggregations=aggregations,
            metric_names=[metric_name],
            timespan=d,

        )
        for dp in o.metrics[0].timeseries[0].data:
            n = Datapoint(
                Minimum=dp.minimum,
                Maximum=dp.maximum,
                Average=dp.average
            )
            datum = Datum(
                Timestamp=dp.timestamp.timestamp(),
                cpu=n
            )
            data.append(datum)

    except Exception as e:
        print(e)
        pass

    return data


def get_instances(
        sub_id: str,
        path_to_output: str = "./",
        dry=False,
        log=None
        ):

    if not dry:
        my_instances = []
        metrics = []
        client = ComputeManagementClient(
                credential=DefaultAzureCredential(),
                subscription_id=sub_id
            )
        metrics_client = MetricsQueryClient(
                credential=DefaultAzureCredential(),
                subscription_id=sub_id
            )
        networkClient = NetworkManagementClient(
                credential=DefaultAzureCredential(),
                subscription_id=sub_id
            )

        res = client.virtual_machines.list_all()

        for vm in res:
            try:
                s = vm.storage_profile.os_disk.managed_disk.id
                tgt = s.split('resourceGroups/')[1]
                tgt = tgt.split('/')[0]
                name = vm.name
                location = vm.location
                hw = vm.hardware_profile.vm_size
                iv = client.virtual_machines.instance_view(
                        vm_name=name,
                        resource_group_name=tgt
                    )
                status = iv.statuses[-1]
                network_interface = vm.network_profile.network_interfaces[0]
                nic_name = network_interface.id.split("networkInterfaces/")[1]
                nics = networkClient.network_interface_ip_configurations.list(
                        resource_group_name=tgt,
                        network_interface_name=nic_name
                    )
                subnet = ""
                public_ip = "n/a"
                for nic in nics:
                    subnet = nic.subnet.name
                    vnet_name = nic.subnet.id.split('/')[-3]
                    if (
                        hasattr(nic, "public_ip_address") and
                        hasattr(nic.public_ip_address, "ip_address")
                    ):
                        public_ip_name = nic.public_ip_address.id.split('/')[-1]  # noqa: E501
                        pi = networkClient.public_ip_addresses.get(tgt, public_ip_name)  # noqa: E501
                        public_ip = pi.ip_address
                architecture = "x86_64"

                if "D2p" in hw or "E2p" in hw:
                    architecture = "Arm"

                my_instance = {
                    "id": vm.id,
                    "name": name,
                    "type": hw,
                    "state": status.display_status,
                    "zone": vm.zones[0] if vm.zones else None,
                    "region": location,
                    "subnet": subnet,
                    "architecture": architecture,
                    "publicIp": public_ip,
                    "vpc": vnet_name
                }
            except Exception as e:
                if log:
                    log(
                        tag="Azure Get Instance Error",
                        msg=str(e)
                    )
                continue
            my_instances.append(my_instance)
            m = get_metrics_for_instance(
                metrics_client=metrics_client,
                instance_id=vm.id,
                instance_name=name
            )
            d = {
                "id": vm.id,
                "metrics": [metric.dict for metric in m]
            }
            metrics.append(d)
        upload = {
                    "metadata": {
                        "provider": "azure",
                        "account": str(sub_id)
                    },
                    "data": my_instances
                }
    # End dry block

    azure_output_file = os.path.join(
        path_to_output,
        f'az-instances-{sub_id}.json'
    )
    if not dry:
        with open(azure_output_file, 'w') as outfile:
            outfile.write(json.dumps(upload, indent=4))

        upload['data'] = metrics
        with open(azure_output_file[:-5]+"-utilization.json", "w") as outfile2:
            outfile2.write(json.dumps(upload, indent=4))
    return azure_output_file

# Test code
# print(get_instances(sub_id="80dc7a6b-df94-44be-a235-7e7ade335a3c"))
