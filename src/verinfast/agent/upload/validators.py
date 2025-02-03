import os
from pathlib import Path


def validate_upload_params(route, file, log):
    """
    Validate upload parameters
    Args:
        route (str): Upload route
        file (str): File path
        log (callable): Logging function
    Returns:
        bool: True if parameters are valid, False otherwise
    """
    if not route:
        log(msg="No route specified for upload", tag="ERROR")
        return False

    if not file:
        log(msg="No file specified for upload", tag="ERROR")
        return False

    if not os.path.exists(file):
        log(msg=f"File does not exist: {file}", tag="ERROR")
        return False

    if not os.path.isfile(file):
        log(msg=f"Not a file: {file}", tag="ERROR")
        return False

    try:
        file_size = os.path.getsize(file)
        if file_size == 0:
            log(msg=f"File is empty: {file}", tag="ERROR")
            return False
    except Exception as e:
        log(msg=f"Error checking file size: {str(e)}", tag="ERROR")
        return False

    return True


def validate_route(route):
    """Validate upload route"""
    valid_routes = [
        "findings",
        "stats",
        "dependencies",
        "costs",
        "instances",
        "storage",
        "utilization",
    ]
    return route in valid_routes


def validate_file_name(filename):
    """Validate file name"""
    try:
        path = Path(filename)
        return all(c not in '<>:"/\\|?*' for c in str(path.name))
    except Exception:
        return False


def validate_json_content(content):
    """Validate JSON content structure"""
    required_fields = ["filename", "size", "id", "source"]
    return all(field in content for field in required_fields)
