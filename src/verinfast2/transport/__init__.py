"""Getting results to the server: URL construction, HTTP, retry, shaping.

``paths`` and ``payloads`` are pure and import eagerly. ``client`` is
**deliberately lazy**: it needs ``httpx``, and importing this package must not
drag an HTTP stack into a caller that only wanted to build a path or truncate
a payload. ``verinfast2.config.schema`` imports ``paths`` from here, so an
eager client import would put httpx behind ``from verinfast2 import
ScanConfig`` — and behind ATD's vendored port of ``paths``, which is supposed
to be copyable precisely because it depends on nothing.

``from verinfast2.transport import Uploader`` still works; it just resolves on
first access (PEP 562) rather than at import time.
"""

from typing import TYPE_CHECKING, Any

from verinfast2.transport.paths import UploadConfig, routes, upload_path
from verinfast2.transport.payloads import (
    NO_TRUNCATE,
    cloud_envelope,
    truncate,
    truncate_findings,
)

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from verinfast2.transport.client import (
        RETRYABLE,
        RetryPolicy,
        Uploader,
        UploadResult,
    )

_LAZY = {"RETRYABLE", "RetryPolicy", "Uploader", "UploadResult"}

__all__ = [
    "NO_TRUNCATE",
    "RETRYABLE",
    "RetryPolicy",
    "UploadConfig",
    "UploadResult",
    "Uploader",
    "cloud_envelope",
    "routes",
    "truncate",
    "truncate_findings",
    "upload_path",
]


def __getattr__(name: str) -> Any:
    """Resolve the HTTP client's names on first use."""
    if name in _LAZY:
        from verinfast2.transport import client

        return getattr(client, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
