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

## Two behaviour changes worth knowing about

**`signed` will differ from every historical scan.** v1 ran
`git show --format='%G?'`, which returns the value wrapped in the format
string's literal quotes, so the comparison against a bare `"N"` never matched
and every commit was recorded as signed. The value here is the real one.
Whether ATD backfills the old rows is `Q7`.

**The git window now means what it says.** git parses a bare `2024-02-22`
with *approxidate*, which fills in the **current time of day** — so
`--since=2024-02-22` run at 18:00 silently means `2024-02-22T18:00`, and a
commit made that morning is dropped. ATD sends a bare `YYYY-MM-DD` and v1
passed it straight through, so every scan has had this: the same scan of the
same repository returned different history depending on what time it ran.
`since_argument` pins midnight.

## Path form, and why it is load-bearing

`sizes` and `stats` both emit `./`-prefixed paths. ATD merges
`ReportCodeFile` rows by path, and it rewrites modernmetric's `temp_repo/…`
paths to `./…` on ingest — a workaround for v1 handing modernmetric absolute
paths inside `~/.verinfast/temp_repo`. ATD's own contract test demonstrates
the split that causes: `sizes` sends `src/compiler.py`, `stats` sends the
rewritten `./src/compiler.py`, and ATD ends up with **two rows for one file**.

modernmetric echoes back exactly the paths it is given, so the filelist
decides the output. Feed it `./src/engine.py` and ATD's rewrite becomes a
no-op and the rows merge. If these two scanners ever disagree on path form,
every per-file join silently halves — there is a test asserting they agree.

## One walk per target

`sizes` and `stats` both need every file under a target. `ScanContext.files_in`
memoises the list, so the tree is walked once for the whole scan rather than
once per scanner — the same waste `N12` exists to remove, just moved from
inside one scanner to between two.

## Current state

| Scanner | State |
| ------- | ----- |
| `git` | implemented |
| `sizes` | implemented |
| `stats` | implemented |
| `findings` | stub — ruleset loading is done; the run is not |
| `dependencies` | stub |

`registry()` returns only the scanners that exist. An artifact missing from it
is a **recorded skip with a reason**, never a silent absence — a clean scan
and a scan that never ran must not look alike (`F18`).
