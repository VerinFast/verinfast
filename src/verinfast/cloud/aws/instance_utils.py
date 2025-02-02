"""AWS Instance Data Processing Utilities"""
from typing import Dict, Any, Optional


def process_instance_data(instance: Dict[str, Any], region: str) -> Dict[str, Any]:
    """Process raw AWS instance data into standardized format"""
    # Get instance name from tags
    name = _get_instance_name(instance)

    # Get placement information
    zone, region = _get_placement_info(instance)

    # Get network information
    subnet_id = instance.get('SubnetId', 'n/a')
    public_ip = _get_public_ip(instance)

    # Build base result
    result = {
        "id": instance["InstanceId"],
        "name": name,
        "state": instance["State"]["Name"],
        "type": instance['InstanceType'],
        "zone": zone if zone else 'n/a',
        "region": region if region else 'n/a',
        "subnet": subnet_id,
        "architecture": instance['Architecture'],
        "vpc": instance.get('VpcId', 'n/a'),
        "publicIp": public_ip
    }

    return result


def _get_instance_name(instance: Dict[str, Any]) -> str:
    """Extract instance name from tags"""
    tags = instance.get('Tags')
    if not tags:
        return instance["InstanceId"]

    name_tags = [t['Value'] for t in tags if t['Key'] == 'Name']
    return name_tags[0] if name_tags else instance["InstanceId"]


def _get_placement_info(instance: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract zone and region from placement information"""
    zone = None
    region = None

    placement = instance.get('Placement', {})
    if 'AvailabilityZone' in placement:
        zone = placement['AvailabilityZone']
        region = zone[0:-1]  # Region is zone without the last character

    return zone, region


def _get_public_ip(instance: Dict[str, Any]) -> str:
    """Get public IP from instance data"""
    # First check direct public IP
    if "PublicIpAddress" in instance:
        return instance['PublicIpAddress']

    # Then check network interfaces
    if "NetworkInterfaces" in instance:
        for interface in instance["NetworkInterfaces"]:
            if 'Association' in interface:
                association = interface['Association']
                if 'PublicIp' in association:
                    return association['PublicIp']

    return 'n/a'
