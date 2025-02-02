from dataclasses import dataclass
from typing import Optional
from ..utils.printable import Printable


@dataclass
class UploadConfig(Printable):
    """Upload configuration

    Args:
        uuid (bool): Use UUID path prefix
        prefix (str): URL prefix (defaults to "/report")
        code_separator (str): Code path separator
        cost_separator (str): Cost path separator
    """
    uuid: bool = False
    prefix: Optional[str] = "/report/"
    code_separator: Optional[str] = "/CorsisCode"
    cost_separator: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.prefix:
            if not isinstance(self.prefix, str):
                raise TypeError("prefix must be a string")
            if not self.prefix.startswith('/'):
                self.prefix = f"/{self.prefix}"
