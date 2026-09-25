"""Dependency and licence inventory across nine ecosystems.

``parsers`` are pure and offline; ``walk`` finds manifests and orchestrates;
``registry`` is the only part that talks to the network.
"""

from verinfast2.dependencies.models import Entry
from verinfast2.dependencies.walk import Walk, deduplicate, discover, preferred

__all__ = ["Entry", "Walk", "deduplicate", "discover", "preferred"]
