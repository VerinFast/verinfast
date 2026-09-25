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
- **dependencies** — lockfile-first; no package manager is ever run.

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

## A platform bug worth knowing about

modernmetric analyses files through a `multiprocessing.Pool`. A function
pickles by `__module__` + `__qualname__`, and under `python -m modernmetric`
that module is `"__main__"` — which in a **spawned** child is the `-m`
launcher, not modernmetric. The child raises `AttributeError`, the parent
times out, and `__main__.py` drops the file:

```python
if file_result is None:
    continue
```

Every file. The run **exits 0 with an empty `files` map**, having spent
`files × file_timeout` seconds getting there.

`fork` hides it entirely, which is why Linux never saw it. macOS defaults to
`spawn` — so on the platform most customer laptops run, code statistics were
silently empty and the scan was very slow. Running the console script instead
makes `modernmetric.__main__` an ordinary imported module, the qualified name
resolves in the child, and it works under either start method.

`StatsScanner._check_coverage` is the safety net: a run that analysed none of
the files it was given is a **failure**, not an empty result. That is `F18`
applied to a tool that fails silently by design.

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
| `dependencies` | implemented — see `../dependencies/` |
| `findings` | implemented |

All five code scanners are wired through `registry()`. Every artifact gets an
outcome; anything that is not `ok` carries a reason, because a clean scan and
a scan that never ran must not look alike (`F18`).

`_scan_cloud` is still unwired — that is where the `user_activity` and
`load_balancers` collectors ATD is waiting on (`F8`) would go.

## The findings engine is a binary

Opengrep is not a PyPI package, so it may be absent. A missing engine is a
**failure**, not a skip: findings were asked for and there are none, and the
operator has an install problem. How the binary ships is action item 19 in
the dependency review, still open.

Tests use a stub engine — a small executable that behaves like the real one —
so the argv, the `cwd` and the environment are exercised end to end without
it. Two tests need the real binary and skip cleanly without it.
