# scanners/

One module per code artifact, all behind one protocol.

| File | Artifact | Ports from |
| ---- | -------- | ---------- |
| `base.py` | — | the `CodeScanner` protocol and the registry |
| `git.py` | `git` | `agent.py::parseRepo` + `formatGitHash` |
| `sizes.py` | `sizes` | `agent.py::parseRepo` (`get_raw_size`, `getloc`) |
| `stats.py` | `stats` | `agent.py::parseRepo` (the modernmetric call) |
| `findings.py` | `findings` | `code_scan.py::run_scan` |
| `dependencies.py` | `dependencies` | `dependencies/walk.py` + `walkers/` |

## The contract

A scanner collects one artifact from one target and **returns** a result — it
does not raise, does not print, does not change the working directory, and
does not modify the tree it is scanning. One scanner failing must leave the
other four unaffected.

## What each one has to fix

- **git** — stop running `git init` against the scan target; one `git log`
  instead of six subprocesses per commit.
- **sizes** — one filesystem traversal instead of three; don't line-count
  binaries; use the configured exclusion list.
- **stats** — subprocess modernmetric instead of calling its `__main__.main()`;
  emit repo-relative paths.
- **findings** — subprocess the engine; drop `--config auto` for a pinned,
  explicitly-licensed ruleset.
- **dependencies** — lockfile-first; package-manager execution is opt-in and
  refused in library mode.

## Current state

`base.py` defines the protocol. Every scanner is a stub whose docstring names
the v1 source and the defects to fix. `registry()` is not wired.
