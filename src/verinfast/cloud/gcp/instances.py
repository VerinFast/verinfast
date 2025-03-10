from datetime import datetime
import json
import os
import time
from typing import List

from google.api_core.exceptions import NotFound
from google.cloud import compute_v1
from google.cloud.monitoring_v3 import (
    Aggregation,
    MetricServiceClient,
    TimeInterval,
    ListTimeSeriesRequest,
)

from verinfast.cloud.gcp.zones import zones
from verinfast.cloud.cloud_dataclass import (
    Utilization_Datapoint as Datapoint,
    Utilization_Datum as Datum,
)

# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/jason/.config/gcloud/application_default_credentials.json"

metric_identifiers = {
    "cpu": "compute.googleapis.com/instance/cpu/utilization",
    "hdd": "agent.googleapis.com/disk/percent_used",  # multiple
    "mem": "agent.googleapis.com/memory/percent_used",
}

metrics = []

now = time.time()
seconds = int(now)
start_seconds = seconds - (30 * 24 * 60 * 60)  # 30 days ago
nanos = int((now - seconds) * 10**9)
interval = TimeInterval(
    {
        "end_time": {"seconds": seconds, "nanos": 0},
        "start_time": {"seconds": start_seconds, "nanos": 0},
    }
)

mean_aggregation = Aggregation(
    {
        "alignment_period": {"seconds": 3600},  # 60 minutes
        "per_series_aligner": Aggregation.Aligner.ALIGN_MEAN,
        "cross_series_reducer": Aggregation.Reducer.REDUCE_MEAN,
    }
)

min_aggregation = Aggregation(
    {
        "alignment_period": {"seconds": 3600},  # 60 minutes
        "per_series_aligner": Aggregation.Aligner.ALIGN_MIN,
        "cross_series_reducer": Aggregation.Reducer.REDUCE_MIN,
    }
)

max_aggregation = Aggregation(
    {
        "alignment_period": {"seconds": 3600},  # 60 minutes
        "per_series_aligner": Aggregation.Aligner.ALIGN_MAX,
        "cross_series_reducer": Aggregation.Reducer.REDUCE_MAX,
    }
)

aggregations = {
    "min": min_aggregation,
    "mean": mean_aggregation,
    "max": max_aggregation,
}


def get_metrics_for_instance(sub_id: str, instance_name: str) -> List[Datum]:
    metrics_client = MetricServiceClient()
    results_dict = {}
    for m in metric_identifiers:
        metric = metric_identifiers[m]
        for a in aggregations:
            aggregation = aggregations[a]
            request = ListTimeSeriesRequest(
                filter=f'metric.type = "{metric}" AND metric.labels.instance_name = "{instance_name}"',
                view=ListTimeSeriesRequest.TimeSeriesView.FULL,
                aggregation=aggregation,
                name=f"projects/{sub_id}",
                interval=interval,
            )
            try:
                results = metrics_client.list_time_series(request=request)
                for result in results:
                    for point in result.points:
                        d = str(
                            datetime.fromtimestamp(
                                point.interval.start_time.timestamp()
                            )
                        )
                        if d not in results_dict:
                            results_dict[d] = {}
                        if m not in results_dict[d]:
                            results_dict[d][m] = {}
                        results_dict[d][m][a] = point.value.double_value * 100
                        results_dict[d]["t"] = point.interval.start_time.timestamp()
            except NotFound:
                pass
    data = []
    for t in results_dict:
        p = results_dict[t]
        temp = {}
        for k in p:
            if k != "t":
                t2 = {}
                if "mean" in p[k]:
                    t2["Average"] = p[k]["mean"]
                else:
                    t2["Average"] = 0
                if "max" in p[k]:
                    t2["Maximum"] = p[k]["max"]
                else:
                    t2["Maximum"] = 0
                if "min" in p[k]:
                    t2["Minimum"] = p[k]["min"]
                else:
                    t2["Minimum"] = 0
                my_datapoint = Datapoint(**t2)
                temp[k] = my_datapoint
        temp["Timestamp"] = p["t"]
        datum = Datum(**temp)
        data.append(datum)
    return data


def get_instances(sub_id: str, path_to_output: str = "./", dry=False):
    if not dry:
        my_instances = []
        # networks_client = compute_v1.NetworksClient()
        instances_client = compute_v1.InstancesClient()
        for zone in zones:
            for instance in instances_client.list(project=sub_id, zone=zone):
                try:
                    name = instance.name
                    architecture = instance.disks[0].architecture
                    hw = instance.machine_type
                    state = instance.status
                    region = zone[0:-3]
                    z = zone[-1:]
                    nic = instance.network_interfaces[0]
                    subnet = nic.subnetwork
                    public_ip = "n/a"
                    if nic.access_configs:
                        public_ip = nic.access_configs[0].nat_i_p
                    vnet_name = nic.network

                    m = get_metrics_for_instance(sub_id=sub_id, instance_name=name)
                    d = {
                        "id": str(instance.id),
                        "metrics": [metric.dict for metric in m],
                    }
                    metrics.append(d)

                    my_instance = {
                        "id": str(instance.id),
                        "name": name,
                        "type": hw.split("/")[-1],
                        "state": state,
                        "zone": z,
                        "region": region,
                        "subnet": subnet.split("/")[-1],
                        "architecture": architecture,
                        "publicIp": public_ip,
                        "vpc": vnet_name.split("/")[-1],
                    }
                except KeyError:
                    continue
                my_instances.append(my_instance)
        # for network in networks_client.list(project=sub_id):
        #     print(network)
        upload = {
            "metadata": {"provider": "gcp", "account": str(sub_id)},
            "data": my_instances,
        }
    # End dry check
    gcp_output_file = os.path.join(path_to_output, f"gcp-instances-{sub_id}.json")
    if not dry:
        with open(gcp_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))

        upload["data"] = metrics
        with open(gcp_output_file[:-5] + "-utilization.json", "w") as outfile2:
            outfile2.write(json.dumps(upload, indent=4))

    return gcp_output_file


# Test code
# get_instances(sub_id="startupos-328814")
