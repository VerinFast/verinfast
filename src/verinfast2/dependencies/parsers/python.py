"""Python: ``requirements*.txt``/``.in``, ``Pipfile``, ``pyproject.toml``,
``poetry.lock``.

Everything here reads the file and nothing else. v1 resolved requirement
files through **johnnydep**, which downloads candidate wheels to compute a
transitive tree — a fair amount of network and disk for metadata, and the
thing *Dependency & License Review* action item 11 flags for replacement.

What that costs and what it does not:

- ``poetry.lock`` already pins the full transitive set, so nothing is lost.
- A ``requirements.txt`` produced by ``pip-compile`` is likewise complete.
- A hand-written ``requirements.txt`` lists only direct dependencies, so the
  transitive tail is not reported. v1 reported it.

Declared-versus-resolved is visible in the artifact: an entry from a lockfile
carries an exact ``==`` pin, one from a manifest carries whatever range was
written. ATD stores the specifier verbatim either way.
"""

from __future__ import annotations

import re
import tomllib
from typing import Any

from verinfast2.dependencies.models import Entry

SOURCE = "pip"

#: A PEP 508 requirement: name, optional extras, optional specifier.
_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9._-]+)\s*(?:\[(?P<extras>[^\]]*)\])?\s*(?P<spec>.*)$"
)

#: Lines that configure pip rather than name a requirement.
_OPTION_PREFIXES = ("-", "--")


def _split_requirement(line: str) -> tuple[str, str | None] | None:
    """``("requests", "==2.31.0")`` from one requirement line."""
    # Strip a comment, then an environment marker: both are trailing context,
    # not part of the package identity.
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(_OPTION_PREFIXES):
        return None
    line = line.split(";", 1)[0].strip()
    if not line or line.startswith(("http://", "https://", "git+", ".", "/")):
        return None
    match = _REQUIREMENT.match(line)
    if not match:
        return None
    spec = match.group("spec").strip()
    return match.group("name"), spec or None


def parse_requirements(text: str, path: str) -> list[Entry]:
    entries: list[Entry] = []
    for raw in text.splitlines():
        parsed = _split_requirement(raw)
        if parsed is None:
            continue
        name, spec = parsed
        entries.append(Entry(name=name, source=SOURCE, specifier=spec))
    return entries


def poetry_specifier(spec: str) -> str:
    """Poetry's ``^`` and ``~`` in PEP 440 terms.

    ``^1.2.3`` is "compatible within the major version", except below 1.0
    where the minor version takes that role — which is why ``^0.2.3`` pins
    much more tightly than ``^1.2.3``.
    """
    spec = spec.strip()
    if spec.startswith("^"):
        version = spec[1:]
        parts = version.split(".")
        try:
            major = int(parts[0])
        except (ValueError, IndexError):
            return spec
        if major > 0:
            return f">={version},<{major + 1}.0.0"
        if len(parts) > 1:
            try:
                minor = int(parts[1])
            except ValueError:
                return spec
            return f">={version},<0.{minor + 1}.0"
        return f">={version},<1.0.0"
    if spec.startswith("~"):
        version = spec[1:]
        parts = version.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            return spec
        return f">={version},<{major}.{minor + 1}.0"
    return spec


def _declared(name: str, spec: Any, convert: bool) -> Entry | None:
    """One entry from a ``name: spec`` pair in TOML."""
    if name.lower() == "python":
        return None
    if isinstance(spec, dict):
        spec = spec.get("version", "*")
    if not isinstance(spec, str):
        return None
    spec = spec.strip()
    if spec in ("", "*"):
        return Entry(name=name, source=SOURCE)
    return Entry(
        name=name,
        source=SOURCE,
        specifier=poetry_specifier(spec) if convert else spec,
    )


def _load_toml(text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError):
        return {}


def parse_pipfile(text: str, path: str) -> list[Entry]:
    document = _load_toml(text)
    entries: list[Entry] = []
    for section in ("packages", "dev-packages"):
        for name, spec in (document.get(section) or {}).items():
            entry = _declared(name, spec, convert=False)
            if entry:
                entries.append(entry)
    return entries


def parse_pyproject(text: str, path: str) -> list[Entry]:
    document = _load_toml(text)
    entries: list[Entry] = []

    # PEP 621.
    project = document.get("project") or {}
    declared = list(project.get("dependencies") or [])
    for group in (project.get("optional-dependencies") or {}).values():
        declared.extend(group)
    for line in declared:
        if not isinstance(line, str):
            continue
        parsed = _split_requirement(line)
        if parsed:
            entries.append(Entry(name=parsed[0], source=SOURCE, specifier=parsed[1]))

    # Poetry.
    poetry = (document.get("tool") or {}).get("poetry") or {}
    for name, spec in (poetry.get("dependencies") or {}).items():
        entry = _declared(name, spec, convert=True)
        if entry:
            entries.append(entry)
    return entries


def parse_poetry_lock(text: str, path: str) -> list[Entry]:
    """The resolved set. Versions are already exact, so nothing is inferred."""
    document = _load_toml(text)
    entries: list[Entry] = []
    seen: set[str] = set()
    for package in document.get("package") or []:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        version = package.get("version")
        if not name or name in seen:
            continue
        seen.add(name)
        entries.append(
            Entry(
                name=name,
                source=SOURCE,
                specifier=f"=={version}" if version else None,
                summary=package.get("description") or None,
            )
        )
    return entries
