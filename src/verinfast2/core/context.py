"""Per-scan state, passed explicitly instead of reached for.

v1 kept this in module globals: a ``template_definition`` dict every stage
mutated, a fixed ``~/.verinfast/temp_repo`` clone path, a ``~/.verinfast_cache``
database, and ``os.chdir()`` as control flow. Together those are why two scans
cannot run in one process (`D5`, `L3`, `L4`).

A :class:`ScanContext` is created per scan, owns its own directories, and is
handed to every scanner. Nothing is global.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from verinfast2.config.schema import ScanConfig

#: Called with (message, fraction_complete). The library never prints; the
#: CLI passes something that does (`L5`, `N11`).
ProgressFn = Callable[[str, float | None], None]


def _noop_progress(message: str, fraction: float | None = None) -> None:
    """Default: progress goes nowhere."""


@dataclass
class ScanContext:
    """Everything a scanner is allowed to reach for.

    Attributes:
        config: the scan's configuration.
        work_dir: scratch space, including repository clones. Unique per
            scan, never the fixed ``~/.verinfast/temp_repo`` (`S14`).
        output_dir: where artifacts are written, when ``write_files``.
        log: a standard logger. Not a bespoke file-appending class (`N9`).
        progress: progress callback.
    """

    config: ScanConfig
    work_dir: Path
    output_dir: Path | None
    log: logging.Logger
    progress: ProgressFn = _noop_progress
    _owns_work_dir: bool = field(default=False, repr=False)
    #: Per-target file lists, memoised. See :meth:`files_in`.
    _file_lists: dict[str, list[str]] = field(default_factory=dict, repr=False)

    @property
    def embedded(self) -> bool:
        return self.config.embedded

    def files_in(self, target: str, walk: Callable[[], list[str]]) -> list[str]:
        """The repo-relative file list for *target*, computed at most once.

        ``sizes`` and ``stats`` both need every file under a target. Walking
        a large monorepo twice is the same waste `N12` exists to remove — it
        just moves the second traversal from inside one scanner to between
        two. The list lives here because it is per-scan derived state, which
        is what a context is for; ``walk`` is called only on a miss.

        Paths are ``./``-prefixed, the form both artifacts must emit so ATD
        merges their rows rather than creating two per file.
        """
        if target not in self._file_lists:
            self._file_lists[target] = walk()
        return self._file_lists[target]

    def scratch_for(self, target: str, kind: str) -> Path:
        """A scratch directory for *target*, guaranteed to stay inside
        :attr:`work_dir`.

        ``target`` is caller-controlled — :class:`~verinfast2.models.ScanTarget`
        is public and ``scan_path(name=...)`` takes whatever it is given — so
        joining it to a path directly lets a name like ``../../etc`` or an
        absolute path escape the scan's workspace. The name is reduced to
        safe characters and disambiguated with a digest of the original, so
        two targets that slugify alike still get separate directories.
        """
        safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in target)
        safe = safe.strip(".-")[:48] or "target"
        digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:8]
        path = self.work_dir / kind / f"{safe}-{digest}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def artifact_path(self, target: str, name: str) -> Path | None:
        """Where ``<target>.<name>.json`` goes, or None if not writing files.

        Returns None — writing nothing — when there is no output directory or
        ``write_files`` is off. In library mode both are the default, so an
        embedded caller that names no output directory gets no files
        anywhere, including under ``~``.

        An ``output_dir`` the caller supplied explicitly is honoured wherever
        it points. The guarantee is that the library never *chooses* a path
        under the home directory, not that it refuses one it was handed.
        """
        if self.output_dir is None or not self.config.write_files:
            return None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir / f"{target}.{name}.json"


@contextmanager
def scan_context(
    config: ScanConfig,
    *,
    log: logging.Logger | None = None,
    progress: ProgressFn | None = None,
) -> Iterator[ScanContext]:
    """Build a context, and clean up its scratch space on the way out.

    A work directory we created is removed in a ``finally``; if removal
    fails it is logged at warning level rather than discarded, because the
    consequence is a leftover clone on someone else's disk.

    The work directory is removed in a ``finally``, so an exception mid-scan
    does not leave a clone behind — v1 only deleted it on the happy path.
    """
    owns = config.work_dir is None
    work_dir = Path(tempfile.mkdtemp(prefix="verinfast-")) if owns else config.work_dir
    assert work_dir is not None
    work_dir.mkdir(parents=True, exist_ok=True)

    ctx = ScanContext(
        config=config,
        work_dir=work_dir,
        output_dir=config.output_dir,
        log=log or logging.getLogger("verinfast"),
        progress=progress or _noop_progress,
        _owns_work_dir=owns,
    )
    try:
        yield ctx
    finally:
        if owns:
            try:
                shutil.rmtree(work_dir)
            except OSError as exc:
                # Reported, not swallowed: an undeletable scratch tree means
                # a scanner left a handle open or the OS refused removal, and
                # it leaves a clone on the caller's disk. `N10`.
                ctx.log.warning(
                    "could not remove scan work directory %s: %s", work_dir, exc
                )
