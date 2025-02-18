from dataclasses import dataclass
from typing import Optional
from ..utils.printable import Printable
from ..constants import DEFAULT_START, DEFAULT_END


@dataclass
class CloudProvider(Printable):
    """Cloud Provider configuration

    Args:
        provider (str): Provider type ('aws', 'gcp', or 'azure')
        account (str | int): Account identifier
        profile (str, optional): Credentials profile
        start (str): Start date (YYYY-MM-DD)
        end (str): End date (YYYY-MM-DD)
    """
    provider: str
    account: str | int
    profile: Optional[str] = None
    start: str = DEFAULT_START
    end: str = DEFAULT_END
