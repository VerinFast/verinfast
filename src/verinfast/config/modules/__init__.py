from dataclasses import dataclass, field
from typing import List, Optional

from .code import CodeModule, GitModule
from .cloud import CloudProvider
from ..utils.printable import Printable


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
        """Validate module configuration"""
        if self.code is None:
            self.code = CodeModule(git=GitModule())
        if not isinstance(self.cloud, list):
            raise TypeError("Cloud providers must be a list")
        for provider in self.cloud:
            if not isinstance(provider, CloudProvider):
                raise TypeError(
                    f"Expected CloudProvider, got {type(provider)}"
                )


__all__ = ['ConfigModules', 'CodeModule', 'CloudProvider']
