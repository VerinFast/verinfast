"""Building a :class:`~verinfast2.config.schema.ScanConfig` from somewhere.

Three sources, one shape. Each is an explicit call — nothing here runs
because a module was imported.

The YAML key names are ATD v3's: its ``services/code_scan.py`` emits exactly
this document at ``GET /api/agent/config/{uuid}/VerinFastConfig.yaml``, so
the reader must keep accepting them unchanged (`A7`, `F11`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verinfast2.config.schema import ScanConfig

__all__ = ["from_dict", "from_file", "from_url", "from_yaml"]


def from_dict(document: dict[str, Any]) -> ScanConfig:
    """Build a config from a parsed agent-config document.

    Raises:
        NotImplementedError: not yet ported. The mapping is mechanical —
            see ``src/verinfast/config.py::handle_config_file`` for the key
            names, and `D1`/`D2` for the two it gets wrong.
    """
    raise NotImplementedError("config.loaders.from_dict")


def from_yaml(text: str) -> ScanConfig:
    """Parse an agent-config YAML document. Wraps :func:`from_dict`."""
    raise NotImplementedError("config.loaders.from_yaml")


def from_file(path: str | Path) -> ScanConfig:
    """Read and parse a local agent-config file."""
    raise NotImplementedError("config.loaders.from_file")


def from_url(url: str, *, timeout: float = 30.0) -> ScanConfig:
    """Fetch and parse a served agent config.

    Unlike v1, the document is parsed in memory and never written to the
    working directory — it carries the report UUID, which is the upload
    credential (`S5`, `D6`).
    """
    raise NotImplementedError("config.loaders.from_url")
