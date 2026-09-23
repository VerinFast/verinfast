"""``verinfast`` on the command line.

Builds a :class:`~verinfast2.config.schema.ScanConfig` from argv plus a
config file or URL, runs a :class:`~verinfast2.core.scanner.Scanner`, and
prints what happened.

Precedence, unchanged from v1 and from what ATD serves: config file, then
command-line arguments on top (`F11`).
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """The argument parser.

    Never give an argument a default here. A default shows up in the parsed
    namespace indistinguishably from something the user typed, and then
    overwrites a value the config file set — v1 documented this trap in a
    comment and it still applies.
    """
    raise NotImplementedError("cli.main.build_parser")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code.

    Returns a code rather than calling ``exit()`` so it stays testable and
    so nothing in the library can take the process down (`L5`).
    """
    raise NotImplementedError("cli.main.main")
