import os
import yaml
from typing import Dict, Any
from pathlib import Path
import httpx
from uuid import uuid4

from verinfast.config.modules import ConfigModules
from ..constants import SUPPORTED_PROTOCOLS, PROTOCOL_SEPARATOR
from ..modules.code import GitModule, CodeModule
from ..modules.cloud import CloudProvider


def is_remote_path(path: str) -> bool:
    """Check if config path is remote URL

    Args:
        path (str): Config file path
    Returns:
        bool: True if path is remote URL
    """
    for protocol in SUPPORTED_PROTOCOLS:
        if path.lower().startswith(protocol + PROTOCOL_SEPARATOR):
            return True
    return False


def fetch_remote_config(path: str) -> str:
    """Fetch remote config file

    Args:
        path: Remote URL to fetch config from

    Returns:
        str: Path to local copy of config

    Raises:
        RuntimeError: If fetch fails
    """
    try:
        requestx = httpx.Client(http2=True, timeout=None)
        response = requestx.get(path)
        response.raise_for_status()

        local_path = str(uuid4()) + ".yaml"
        with open(local_path, "wb") as f:
            f.write(response.content)

        return local_path
    except Exception as e:
        raise RuntimeError(f"Failed to fetch remote config: {e}")


def find_config_file(path: str) -> Path:
    """Find config file in current or parent directories

    Args:
        path (str): Initial config path
    Returns:
        Path: Found config file path
    """
    if os.path.isfile(path):
        return Path(path)

    curr_path = Path(os.getcwd())
    while curr_path != curr_path.parent:
        config_path = curr_path.joinpath(path)
        if config_path.exists():
            return config_path
        curr_path = curr_path.parent

    return Path(path)


def parse_config_file(config: Any, path: str) -> Dict:
    """Parse configuration file

    TODO: Add support for JSON config files.
    Currently only supports YAML format.

    Args:
        config: Config instance to update
        path: Path to config file

    Returns:
        dict: Parsed configuration data
    """
    if not os.path.isfile(path):
        return {}

    with open(path) as f:
        data = yaml.safe_load(f)

    # Update global settings
    if "baseurl" in data:
        config.baseUrl = data["baseurl"]
    if "should_upload" in data:
        config.shouldUpload = data["should_upload"]
    if "dry" in data:
        config.dry = data["dry"]
    if "delete_temp" in data:
        config.delete_temp = data["delete_temp"]
    if "truncate_findings" in data:
        config.truncate_findings = data["truncate_findings"]
        config.truncate_findings_length = data.get("truncate_findings_length", 30)

    # Handle server settings
    if "server" in data:
        server = data["server"]
        config.server_prefix = server.get("prefix")
        config.server_code_separator = server.get("code_separator")
        config.server_cost_separator = server.get("cost_separator")

    # Handle report settings
    if "report" in data:
        report = data["report"]
        if "uuid" in report:
            config.use_uuid = True
            config.reportId = report["uuid"]
        elif "id" in report:
            config.reportId = report["id"]

    # Handle modules
    if "modules" in data:
        _parse_modules(config, data["modules"])

    return data


def _parse_modules(config: Any, modules: Dict) -> None:
    """Parse module configurations

    Args:
        config: Config instance to update
        modules: Module configuration dictionary
    """
    cloud_modules = []
    if "cloud" in modules:
        for provider_config in modules["cloud"]:
            try:
                provider = CloudProvider(**provider_config)
                cloud_modules.append(provider)
            except Exception as e:
                config.log(f"Error parsing cloud provider config: {str(e)}")

    code_module = None
    if "code" in modules:
        code = modules["code"]
        git_module = GitModule()

        if "git" in code:
            git_config = code["git"]
            if "start" in git_config:
                git_module.start = git_config["start"]

        code_module = CodeModule(git=git_module)

        # Update run flags
        config.runGit = code.get("run_git", False)
        config.runScan = code.get("run_scan", config.runScan)
        config.runSizes = code.get("run_sizes", config.runSizes)
        config.runStats = code.get("run_stats", config.runStats)
        config.runDependencies = code.get("dependencies", config.runDependencies)

    config.modules = ConfigModules(code=code_module, cloud=cloud_modules)
