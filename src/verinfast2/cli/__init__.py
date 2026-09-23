"""The command line. The only place in this package allowed to print.

Everything interactive lives here: argument parsing, consent prompts,
progress output, exit codes. The library underneath never reads ``sys.argv``,
never calls ``input()``, never calls ``print()`` and never calls ``exit()``
(`L1`, `L5`).

That separation is the whole reason for the rewrite. Keep it: if a prompt or
a print is needed by something in ``core/`` or ``scanners/``, it is a
callback that the CLI supplies, not a call the library makes.
"""

from verinfast2.cli.main import main

__all__ = ["main"]
