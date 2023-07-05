import json
import os

from google.cloud import compute_v1

from zones import zones

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/Users/jason/.config/gcloud/application_default_credentials.json"

def get_instances(sub_id:str, path_to_output:str="./"):
    my_instances = []
    networks_client = compute_v1.NetworksClient()
    instances_client = compute_v1.InstancesClient()
    for zone in zones:
        for instance in instances_client.list(project=sub_id, zone=zone):
            name = instance.name
            architecture = instance.disks[0].architecture
            hw = instance.machine_type
            state = instance.status
            region = zone[0:-3]
            z=zone[-1:]
            nic = instance.network_interfaces[0]
            subnet = nic.subnetwork
            public_ip = "n/a"
            if nic.access_configs:
                public_ip = nic.access_configs[0].nat_i_p
            vnet_name = nic.network

            my_instance = {
                "name": name,
                "type": hw.split("/")[-1],
                "state": state,
                "zone": z,
                "region" : region,
                "subnet": subnet.split("/")[-1],
                "architecture": architecture,
                "publicIp": public_ip,
                "vpc": vnet_name.split("/")[-1]
            }
            my_instances.append(my_instance)
    # for network in networks_client.list(project=sub_id):
    #     print(network)
    upload = {
                "metadata": {
                    "provider": "gcp",
                    "account": str(sub_id)
                },
                "data" : my_instances
            }
    gcp_output_file = os.path.join(path_to_output, f'gcp-instances-{sub_id}.json')
    with open(gcp_output_file, 'w') as outfile:
        outfile.write(json.dumps(upload, indent=4))
    return gcp_output_file

# Test code
# get_instances(sub_id="startupos-328814")
