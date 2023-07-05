import json
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient

def get_instances(sub_id:str, path_to_output:str="./"):
    my_instances = []
    client = ComputeManagementClient(credential=DefaultAzureCredential(), subscription_id=sub_id)
    networkClient = NetworkManagementClient(credential=DefaultAzureCredential(), subscription_id=sub_id)
    res = client.virtual_machines.list_all()
    for vm in res:
        s = vm.storage_profile.os_disk.managed_disk.id
        tgt = s.split('resourceGroups/')[1]
        tgt = tgt.split('/')[0]
        name = vm.name
        location = vm.location
        r = vm.resources
        hw = vm.hardware_profile.vm_size
        iv = client.virtual_machines.instance_view(vm_name=name, resource_group_name=tgt)
        status = iv.statuses[-1]
        network_interface = vm.network_profile.network_interfaces[0]
        nic_name = network_interface.id.split("networkInterfaces/")[1]
        nics = networkClient.network_interface_ip_configurations.list(resource_group_name=tgt, network_interface_name=nic_name)
        subnet=""
        public_ip = "n/a"
        for nic in nics:
            subnet = nic.subnet.name
            vnet_name = nic.subnet.id.split('/')[-3]
            if hasattr(nic, "public_ip_address") and hasattr(nic.public_ip_address, "ip_address"):
                public_ip_name = nic.public_ip_address.id.split('/')[-1]
                pi = networkClient.public_ip_addresses.get(tgt, public_ip_name)
                public_ip = pi.ip_address
        architecture = "x86_64"
        if "D2p" in hw or "E2p" in hw:
                architecture="Arm"
        print(status.serialize())
        my_instance = {
            "name": name,
            "type": hw,
            "state": status.display_status,
            "zone": vm.zones[0],
            "region" : location,
            "subnet": subnet,
            "architecture": architecture,
            "publicIp": public_ip,
            "vpc": vnet_name
        }
        my_instances.append(my_instance)
    upload = {
                "metadata": {
                    "provider": "azure",
                    "account": str(sub_id)
                },
                "data" : my_instances
            }
    azure_output_file = os.path.join(path_to_output, f'az-instances-{sub_id}.json')
    with open(azure_output_file, 'w') as outfile:
        outfile.write(json.dumps(upload, indent=4))
    return azure_output_file

# Test code
# print(get_instances(sub_id="80dc7a6b-df94-44be-a235-7e7ade335a3c"))
