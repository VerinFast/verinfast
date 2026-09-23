"""File inventory: sizes, line counts and extensions.

Ports ``src/verinfast/agent.py::parseRepo (get_raw_size, getloc, allowfile)``.

**One traversal, not three.** v1 walked the tree once for the repository
total, once for the ``.git`` total, and once for the file list — then called
``os.path.getsize`` again per file (`D24`, `N12`). Everything here comes out
of a single walk, with ``os.scandir``'s cached stat.

**Binary files are not read line by line to count newlines** (`D26`, `N15`).
A file is sniffed for a NUL byte in its first 8 KiB and skipped if it looks
binary; v1 opened everything in text mode and relied on a bare ``except``.

**The exclusion list comes from config** rather than a hardcoded pair that
ignores the one two directories away (`D10`). ``.git`` is always excluded
regardless — its size is collected separately, for ``metadata.real_size``.

## Path form

Paths are emitted ``./``-prefixed, exactly as v1 emitted them. This is not
cosmetic: ATD merges ``ReportCodeFile`` rows by path, and it rewrites
modernmetric's ``temp_repo/...`` paths to ``./...``. Emitting a bare
``src/engine.py`` here would land it in a *different* row from the same
file's stats — ATD's own contract test demonstrates exactly that split. The
two forms only merge if both artifacts use ``./``.

The ``"."`` root entry and the four ``metadata`` keys are load-bearing: ATD
lifts the root entry's size onto the repository row.
"""

from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Final, Iterator

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget

#: Directories never walked, whatever the config says. ``.git`` is measured
#: separately; the rest are other people's artifacts, not the customer's code.
ALWAYS_SKIP: Final[frozenset[str]] = frozenset({".git", "node_modules"})

#: Bytes sniffed when deciding whether a file is text.
SNIFF_BYTES: Final = 8192

#: v1's extension rule: everything after the first dot, so ``archive.tar.gz``
#: is ``tar.gz`` and ``.gitignore`` is ``gitignore``. Kept because ATD groups
#: on it and two years of rows already use this convention.
_EXT = re.compile(r"^[^.]*\.(.*)")


def extension_of(name: str) -> str:
    """The extension ATD will group on. ``""`` when there is no dot."""
    match = _EXT.search(name)
    return match.group(1) if match else ""


def is_binary(path: Path) -> bool:
    """Whether *path* looks binary, by the NUL-byte heuristic.

    Cheap and wrong at the margins — a UTF-16 text file reads as binary — but
    the consequence is a ``loc`` of 0 on a file whose line count was never
    meaningful, which beats decoding every byte of a 200 MB asset.
    """
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(SNIFF_BYTES)
    except OSError:
        return True


def count_lines(path: Path) -> int:
    """Non-blank lines, v1's definition. Zero for anything unreadable."""
    if is_binary(path):
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


@dataclass(frozen=True)
class _Entry:
    rel: str
    size: int
    is_link: bool


def _excluded(rel: str, patterns: list[str]) -> bool:
    """Whether *rel* matches any configured exclusion glob."""
    return any(
        fnmatch(rel, pattern) or fnmatch(f"./{rel}", pattern) for pattern in patterns
    )


def walk_files(root: Path, exclude: list[str]) -> Iterator[_Entry]:
    """Every file under *root*, once, with its size.

    Symlinks are reported but never followed and never counted — following
    them can leave the scanned tree entirely, and a cycle never terminates
    (`S12`).
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            rel = os.path.relpath(entry.path, root)
            if entry.is_dir(follow_symlinks=False):
                if entry.name in ALWAYS_SKIP or _excluded(rel, exclude):
                    continue
                stack.append(Path(entry.path))
                continue
            if _excluded(rel, exclude):
                continue
            is_link = entry.is_symlink()
            try:
                size = 0 if is_link else entry.stat(follow_symlinks=False).st_size
            except OSError:
                size = 0
            yield _Entry(rel=rel.replace(os.sep, "/"), size=size, is_link=is_link)


def directory_size(root: Path) -> int:
    """Recursive size of one directory, symlinks excluded. Used for ``.git``."""
    total = 0
    stack = [root]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(Path(entry.path))
            else:
                try:
                    total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    return total


class SizesScanner:
    """Collect file sizes, line counts and the file list."""

    artifact = Artifact.SIZES

    def enabled(self, ctx: ScanContext) -> bool:
        return ctx.config.code.sizes

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        if target.path is None:
            return ArtifactResult(
                artifact=self.artifact,
                target=target.name,
                outcome=Outcome.SKIPPED,
                error="no local path for this target",
            )
        root = target.path
        files: dict[str, Any] = {}
        total = 0

        for entry in walk_files(root, ctx.config.exclude):
            total += entry.size
            if entry.is_link:
                # Counted as present, never read, never sized. v1 dropped
                # them entirely, so a symlink-heavy tree looked smaller than
                # it is without saying so.
                continue
            path = root / entry.rel
            files[f"./{entry.rel}"] = {
                "size": entry.size,
                "loc": count_lines(path),
                "ext": extension_of(os.path.basename(entry.rel)),
                "directory": False,
            }

        git_size = directory_size(root / ".git")
        # The root entry's size is the whole tree including .git, matching v1
        # — ATD lifts it onto `repository.file_size`, and changing what that
        # number means would break every historical comparison.
        data = {
            "files": {
                ".": {
                    "size": total + git_size,
                    "loc": 0,
                    "ext": None,
                    "directory": True,
                },
                **files,
            },
            "metadata": {
                "env": platform.machine(),
                "real_size": total,
                "uname": platform.system(),
                "branch": target.branch,
            },
        }
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.OK,
            data=data,
        )
