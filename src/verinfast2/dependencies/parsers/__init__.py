"""One parser per manifest format, and the table that dispatches to them.

Every parser is ``(text, path) -> list[Entry]``: pure, no I/O, no network, no
subprocess. That is what makes them testable from a string and what keeps the
test suite offline (`N16`). Enrichment and anything that runs a command live
above them.

A parser **never raises**. Malformed input from someone else's repository is
expected, not exceptional, and one unparseable ``pom.xml`` must not cost the
other eight ecosystems.
"""

from __future__ import annotations

from typing import Callable, Final

from verinfast2.dependencies.models import Entry
from verinfast2.dependencies.parsers import (
    container,
    dotnet,
    golang,
    javascript,
    jvm,
    php,
    python,
    ruby,
)

Parser = Callable[[str, str], list[Entry]]

#: Filename (or suffix, for ``*.csproj``) to parser. v1 kept nine separate
#: ``manifest_files`` lists on nine walker instances, each of which walked the
#: whole tree looking for its own — nine traversals of a monorepo to find
#: files a single pass sees (`N12`).
MANIFESTS: Final[dict[str, Parser]] = {
    "package.json": javascript.parse_package_json,
    "package-lock.json": javascript.parse_package_lock,
    "requirements.txt": python.parse_requirements,
    "requirements-dev.txt": python.parse_requirements,
    "requirements.in": python.parse_requirements,
    "Pipfile": python.parse_pipfile,
    "pyproject.toml": python.parse_pyproject,
    "poetry.lock": python.parse_poetry_lock,
    "Gemfile": ruby.parse_gemfile,
    "gemfile": ruby.parse_gemfile,
    "Gemfile.lock": ruby.parse_gemfile_lock,
    "pom.xml": jvm.parse,
    "composer.json": php.parse,
    "go.sum": golang.parse,
    "Dockerfile": container.parse,
    "dockerfile": container.parse,
    "docker-compose.yml": container.parse,
    "docker-compose.yaml": container.parse,
}

#: Matched on suffix rather than exact name.
SUFFIXES: Final[dict[str, Parser]] = {".csproj": dotnet.parse}

#: When both are present, the lockfile wins: it has resolved versions, and
#: reporting both doubles every package in the artifact. v1 did this for npm
#: only, and by accident — it fell back to the lockfile when ``npm install``
#: produced nothing.
PREFERRED_OVER: Final[dict[str, str]] = {
    "package-lock.json": "package.json",
    "poetry.lock": "pyproject.toml",
    "Gemfile.lock": "Gemfile",
}


def parser_for(filename: str) -> Parser | None:
    """The parser for *filename*, or None if we do not handle it."""
    if filename in MANIFESTS:
        return MANIFESTS[filename]
    for suffix, parser in SUFFIXES.items():
        if filename.endswith(suffix):
            return parser
    return None


def handled() -> frozenset[str]:
    """Every exact filename the table knows. Used by the walk to filter."""
    return frozenset(MANIFESTS)


__all__ = [
    "MANIFESTS",
    "PREFERRED_OVER",
    "SUFFIXES",
    "Parser",
    "handled",
    "parser_for",
]
