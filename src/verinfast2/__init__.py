"""VerinFast — a portable, low-trust scanning agent.

Scan a repository or a directory of code and get back measurements: git
history, file inventory, code statistics, security findings and a dependency
inventory. Source never leaves the machine; only the summary data does.

Importing this package does nothing observable. It does not read
``sys.argv``, prompt, touch your home directory, patch a third-party library
or open a log file — which is what makes it usable as a library:

    >>> from verinfast2 import ScanConfig, Scanner
    >>> result = Scanner(ScanConfig(embedded=True)).scan_path("/tmp/sample")
    >>> result.ok
    True

``embedded=True`` additionally refuses telemetry, package-manager execution
and writes to the home directory.

The command line is a thin shell over exactly this API; see
:mod:`verinfast2.cli`.
"""

from verinfast2.config.schema import CodeConfig, PrivacyConfig, ScanConfig
from verinfast2.core.scanner import Scanner
from verinfast2.models import (
    Artifact,
    ArtifactResult,
    CloudAccount,
    Outcome,
    ScanResult,
    ScanTarget,
)

__all__ = [
    "Artifact",
    "ArtifactResult",
    "CloudAccount",
    "CodeConfig",
    "Outcome",
    "PrivacyConfig",
    "ScanConfig",
    "ScanResult",
    "ScanTarget",
    "Scanner",
]
