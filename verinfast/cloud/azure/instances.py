import json

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient




def get_instances(sub_id:str, path_to_output:str="./"):
    my_instances = []
    client = ComputeManagementClient(credential=DefaultAzureCredential(), subscription_id=sub_id)
    res = client.virtual_machines.list_all()
    for vm in res:
        print(json.dumps(vm.serialize(), indent=4))
        name = vm.name
        r = vm.resources
        print(r)
        hw = vm.hardware_profile.vm_size
        # v = vm.instance_view
        iv = client.virtual_machines.instance_view(vm_name=name)
        print(iv)
        my_instance = {
            "name": name,
            "type": hw
        }
        my_instances.append(my_instance)
        # print(hw)
        # print(name)
        # print(vm)
    return my_instances

get_instances(sub_id="80dc7a6b-df94-44be-a235-7e7ade335a3c")