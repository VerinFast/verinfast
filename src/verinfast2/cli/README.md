# cli/

The command line. The only place in this package allowed to print.

| File | What |
| ---- | ---- |
| `main.py` | argument parser and `main()` |

## Why this is a separate package

Everything interactive lives here: argument parsing, consent prompts,
progress output, exit codes. The library underneath never reads `sys.argv`,
never calls `input()`, never calls `print()` and never calls `exit()`.

That separation is the reason for the rewrite. v1 mixed them — argv parsing
in `Config.__init__`, an `input()` consent prompt inside `Agent.__init__`, an
`exit(0)` in preflight — and that is precisely what makes it impossible to
import.

## Argument defaults

Don't give arguments defaults in the parser. A default is indistinguishable
from something the user typed, so it overwrites whatever the config file set.
v1 documented this trap in a comment and it still applies.

## Consent

The prompts v1 asked in a constructor become config fields plus a CLI
interaction. A library caller sets `privacy.telemetry` and
`privacy.upload_logs` explicitly; `embedded=True` forces both off, because
there is no human to ask.

## The home directory

Preference and cache storage are CLI concerns. The library never *chooses* a
path under `~`, and an embedded scan that names no `output_dir` writes no
files at all. An `output_dir` supplied explicitly is honoured wherever it
points — refusing one under `~` would break every container whose `HOME` is
the working root.

## Current state

Stub. `build_parser` and `main` raise `NotImplementedError`.
