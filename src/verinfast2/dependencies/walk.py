"""Finding manifests, parsing them, and filling in what the files omit.

Three stages, deliberately separable:

1. **Discover** — one traversal, collecting every file a parser handles.
   v1 gave each of its nine walkers its own ``rglob("**/*")``, so a monorepo
   was walked nine times to find files a single pass sees (`N12`).
2. **Parse** — each file through its parser. Pure, offline, never raises.
3. **Enrich** — look up licences and descriptions the files did not carry.

Stage 3 is the only one that touches the network, and
:class:`~verinfast2.dependencies.registry.RegistryClient` can be disabled
without affecting the first two.

## Lockfiles win

When a directory has both a manifest and its lockfile, only the lockfile is
parsed: it has resolved versions rather than ranges, and parsing both would
report every package twice. The preference is per directory, because a
monorepo's packages each have their own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Final, Iterator

from verinfast2.dependencies.models import Entry
from verinfast2.dependencies.parsers import PREFERRED_OVER, parser_for
from verinfast2.dependencies.registry import RegistryClient

#: Never descended into. A dependency's own vendored tree is not the
#: project's dependency list, and walking ``node_modules`` on a real project
#: costs more than the rest of the scan combined.
SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "node_modules",
        "vendor",
        "bower_components",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        "target",
        "bin",
        "obj",
    }
)

#: Which registry answers for which ``Entry.source``.
_LOOKUPS: Final[dict[str, str]] = {
    "npm": "npm",
    "package-lock.json": "npm",
    "pip": "pypi",
    "gem": "rubygems",
    "nuget": "nuget",
}


@dataclass
class Discovery:
    """One manifest found on disk."""

    path: Path
    #: Path relative to the scan root, ``/``-separated. What goes in the
    #: artifact — never an absolute path from the scanning machine (`S3`).
    rel: str

    @property
    def name(self) -> str:
        return self.path.name


def discover(root: Path, exclude: list[str]) -> list[Discovery]:
    """Every manifest under *root*, in one traversal."""
    found: list[Discovery] = []
    stack = [root]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            rel = os.path.relpath(entry.path, root).replace(os.sep, "/")
            if entry.is_dir(follow_symlinks=False):
                if entry.name in SKIP_DIRS or _excluded(rel, exclude):
                    continue
                stack.append(Path(entry.path))
                continue
            if entry.is_symlink() or _excluded(rel, exclude):
                continue
            if parser_for(entry.name) is not None:
                found.append(Discovery(path=Path(entry.path), rel=rel))
    return sorted(found, key=lambda item: item.rel)


def _excluded(rel: str, patterns: list[str]) -> bool:
    return any(
        fnmatch(rel, pattern) or fnmatch(f"./{rel}", pattern) for pattern in patterns
    )


def preferred(found: list[Discovery]) -> list[Discovery]:
    """Drop a manifest when its lockfile sits in the same directory."""
    by_dir: dict[str, set[str]] = {}
    for item in found:
        by_dir.setdefault(os.path.dirname(item.rel), set()).add(item.name)

    keep: list[Discovery] = []
    for item in found:
        superseded_by = {
            lock for lock, manifest in PREFERRED_OVER.items() if manifest == item.name
        }
        if superseded_by & by_dir.get(os.path.dirname(item.rel), set()):
            continue
        keep.append(item)
    return keep


def parse_all(
    found: list[Discovery], on_error: Callable[[str, Exception], None] | None = None
) -> Iterator[Entry]:
    """Parse each discovered manifest. One bad file costs one file."""
    for item in found:
        try:
            text = item.path.read_text(encoding="utf-8", errors="replace")
            yield from parser_for(item.name)(text, item.rel)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001 — see the module docstring
            if on_error is not None:
                on_error(item.rel, exc)


def deduplicate(entries: Iterator[Entry] | list[Entry]) -> list[Entry]:
    """Collapse entries identical in name, source and specifier.

    A monorepo declares the same dependency in several packages, and v1 sent
    one row per declaration. ATD delete-and-replaces the whole set on ingest,
    so duplicates are pure noise in the payload.
    """
    seen: dict[tuple[str, str, str], Entry] = {}
    for entry in entries:
        key = (entry.name, entry.source, entry.specifier or "")
        existing = seen.get(key)
        if existing is None:
            seen[key] = entry
            continue
        # Keep whichever copy knows more: a lockfile may carry a licence the
        # manifest did not.
        if entry.license and not existing.license:
            existing.license = entry.license
        if entry.summary and not existing.summary:
            existing.summary = entry.summary
    return list(seen.values())


@dataclass
class Walk:
    """Run the three stages over one tree.

    Args:
        registry: used for stage 3. Pass one with ``enabled=False`` — or a
            stub — to keep the whole thing offline.
        warn: called with a human-readable message for anything non-fatal.
    """

    registry: RegistryClient = field(default_factory=RegistryClient)
    warn: Callable[[str], None] | None = None

    def run(self, root: Path, exclude: list[str] | None = None) -> list[Entry]:
        found = preferred(discover(root, exclude or []))
        entries = deduplicate(parse_all(found, on_error=self._on_parse_error))
        self.enrich(entries)
        return sorted(entries, key=lambda e: (e.source, e.name, e.specifier or ""))

    def enrich(self, entries: list[Entry]) -> None:
        """Fill in licence and summary where the manifest had none.

        Only the gaps: a lockfile that already carries a licence is trusted
        over the registry, because it records what was actually installed.
        """
        if not self.registry.enabled:
            return
        for entry in entries:
            if entry.license and entry.summary:
                continue
            lookup = _LOOKUPS.get(entry.source)
            if lookup is None:
                continue
            metadata = getattr(self.registry, lookup)(entry.name, entry.specifier)
            if not entry.license and metadata.get("license"):
                entry.license = metadata["license"]
            if not entry.summary and metadata.get("summary"):
                entry.summary = metadata["summary"]

    def _on_parse_error(self, rel: str, exc: Exception) -> None:
        if self.warn is not None:
            self.warn(f"could not parse {rel}: {type(exc).__name__}: {exc}")
