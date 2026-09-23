"""JavaScript: ``package.json`` and ``package-lock.json``.

``package.json`` names what a project *declares*; ``package-lock.json`` names
what actually gets installed, with resolved versions. Both are parsed — the
lockfile is the better answer when present, and the scanner prefers it.

v1 got its resolved list by running ``npm install`` and then walking
``node_modules`` for every nested ``package.json``. That executes arbitrary
install scripts from the dependency graph of the code being scanned (`S7`),
so it is off by default here and the lockfile covers the same ground.
"""

from __future__ import annotations

import json
from typing import Any

from verinfast2.dependencies.models import Entry

SOURCE = "npm"
LOCK_SOURCE = "package-lock.json"


def _license(value: Any) -> str | None:
    """npm's ``license`` is a string, a ``{"type": ...}``, or a list of either."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("type")
    if isinstance(value, list):
        parts = [
            item.get("type") if isinstance(item, dict) else str(item) for item in value
        ]
        return " ".join(part for part in parts if part) or None
    return None


def _specifier(value: str) -> str:
    """A bare version becomes an exact pin; a range is left alone."""
    return f"=={value}" if value[:1].isdigit() else value


def parse_package_json(text: str, path: str) -> list[Entry]:
    """The declared dependencies of one ``package.json``.

    v1 parsed the *installed* package's own manifest, so it reported the
    package itself rather than what it depends on. Reading the manifest of
    the project being scanned means reading its ``dependencies`` map.
    """
    try:
        document = json.loads(text)
    except ValueError:
        return []
    if not isinstance(document, dict):
        return []

    entries: list[Entry] = []
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        declared = document.get(section)
        if not isinstance(declared, dict):
            continue
        for name, spec in declared.items():
            if not isinstance(spec, str):
                continue
            entries.append(
                Entry(name=name, source=SOURCE, specifier=_specifier(spec) or None)
            )
    return entries


def parse_package_lock(text: str, path: str) -> list[Entry]:
    """Resolved versions from a lockfile, v1 through v3.

    v1 read only the ``dependencies`` map, which lockfile v2 keeps for
    backwards compatibility but v3 drops entirely — so a modern lockfile
    produced nothing at all (`D29`).
    """
    try:
        document = json.loads(text)
    except ValueError:
        return []
    if not isinstance(document, dict):
        return []

    entries: list[Entry] = []
    seen: set[tuple[str, str]] = set()

    def add(name: str, info: dict[str, Any]) -> None:
        version = info.get("version")
        if not name or not isinstance(version, str):
            return
        if (name, version) in seen:
            return
        seen.add((name, version))
        entries.append(
            Entry(
                name=name,
                source=LOCK_SOURCE,
                specifier=version,
                license=_license(info.get("license")),
            )
        )

    # Lockfile v2/v3: keys are install paths like "node_modules/lodash".
    packages = document.get("packages")
    if isinstance(packages, dict):
        for install_path, info in packages.items():
            if not install_path or not isinstance(info, dict):
                # "" is the project itself, not a dependency.
                continue
            name = info.get("name") or install_path.rpartition("node_modules/")[2]
            add(name, info)

    # Lockfile v1, and the compatibility map v2 still writes.
    legacy = document.get("dependencies")
    if isinstance(legacy, dict):
        for name, info in legacy.items():
            if isinstance(info, dict):
                add(name, info)
    return entries
