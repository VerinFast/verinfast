import json
import subprocess
from typing import Dict, Any
import platform
import os


def get_system_info() -> Dict[str, Any]:
    """
    Collects system information using hyfetch and
    returns it as a JSON-compatible dictionary.
    Falls back to basic system info if hyfetch fails.
    """
    try:
        # Run hyfetch
        result = subprocess.run(
            ["hyfetch"],
            capture_output=True,
            text=True,
            # check=True,
            timeout=15  # 15 second timeout
        )

        # Process the output
        lines = result.stdout.split("\n")
        info = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                # Convert keys to snake_case and remove spaces
                key = key.strip().lower().replace(" ", "_")
                info[key] = value.strip()

        # Add additional system information
        info.update(_get_additional_info())

        print(json.dumps(info, indent=4))

    except (subprocess.CalledProcessError, FileNotFoundError,
            subprocess.TimeoutExpired) as e:
        # Fallback to basic system info if hyfetch fails,
        #  isn't installed, or times out
        info = {
            "error": f"Failed to run hyfetch: {str(e)}",
            "system_info": _get_additional_info()
        }

    return info


def _get_additional_info() -> Dict[str, Any]:
    """
    Collects additional system information
    using platform (Python's built-in libraries.
    """
    uname = platform.uname()

    return {
        "os": uname.system,
        "os_release": uname.release,
        "os_version": uname.version,
        "architecture": uname.machine,
        "processor": uname.processor,
        "hostname": uname.node,
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "cpu_architecture": platform.machine(),
        "python_implementation": platform.python_implementation()
    }
