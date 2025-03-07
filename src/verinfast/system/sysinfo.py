from typing import Dict, Any
import platform
import psutil
import shutil


def get_system_info() -> Dict[str, Any]:
    """
    Collects system information and
    returns it as a JSON-compatible dictionary.
    """
    return {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "OS Release": platform.release(),
        "Machine": platform.machine(),
        "Processor": platform.processor(),
        "Hostname": platform.node(),
        "CPU Cores": psutil.cpu_count(logical=False),
        "Logical CPUs": psutil.cpu_count(logical=True),
        "Total RAM": (f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB"),
        "Available RAM": (
            f"{round(psutil.virtual_memory().available / (1024**3), 2)} GB"
        ),
        "Used RAM": f"{round(psutil.virtual_memory().used / (1024**3), 2)} GB",
        "Disk Size": (f"{round(shutil.disk_usage('/').total / (1024**3), 2)} GB"),
        "Disk Used": f"{round(shutil.disk_usage('/').used / (1024**3), 2)} GB",
        "Disk Free": f"{round(shutil.disk_usage('/').free / (1024**3), 2)} GB",
        "Python Version": platform.python_version(),
    }
