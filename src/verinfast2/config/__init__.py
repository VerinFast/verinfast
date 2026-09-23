"""Configuration: the schema, and the three ways to build one."""

from verinfast2.config.loaders import from_dict, from_file, from_url, from_yaml
from verinfast2.config.schema import CodeConfig, PrivacyConfig, ScanConfig

__all__ = [
    "CodeConfig",
    "PrivacyConfig",
    "ScanConfig",
    "from_dict",
    "from_file",
    "from_url",
    "from_yaml",
]
