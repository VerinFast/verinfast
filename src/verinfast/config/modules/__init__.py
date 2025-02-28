from dataclasses import dataclass, field
from typing import List, Optional

from verinfast.config.utils import Printable
from verinfast.config.modules.code import CodeModule, GitModule
from verinfast.config.modules.cloud import CloudProvider


@dataclass
class ConfigModules(Printable):
    """Configuration for all modules

    Args:
        code (CodeModule): Code scanning configuration
        cloud (List[CloudProvider]): List of cloud provider configurations
    """

    code: Optional[CodeModule] = None
    cloud: List[CloudProvider] = field(default_factory=list)

    def __post_init__(self):
        """Initialize and validate module configuration"""
        # Validate cloud providers
        if not isinstance(self.cloud, list):
            raise TypeError("Cloud providers must be a list")
        for provider in self.cloud:
            if not isinstance(provider, CloudProvider):
                raise TypeError(f"Expected CloudProvider, got {type(provider)}")


__all__ = ["ConfigModules", "CodeModule", "GitModule", "CloudProvider"]
