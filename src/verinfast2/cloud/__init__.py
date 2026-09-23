"""Cloud providers: one protocol, three implementations."""

from verinfast2.cloud.aws import AwsProvider
from verinfast2.cloud.azure import AzureProvider
from verinfast2.cloud.base import CloudProvider, provider_for
from verinfast2.cloud.gcp import GcpProvider

__all__ = [
    "AwsProvider",
    "AzureProvider",
    "CloudProvider",
    "GcpProvider",
    "provider_for",
]
