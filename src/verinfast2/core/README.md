# core/

Orchestration, and the per-scan state everything else is handed.

| File | What |
| ---- | ---- |
| `scanner.py` | `Scanner` — decides what runs, collects what comes back |
| `context.py` | `ScanContext` + `scan_context()` — paths, logger, progress |

## ScanContext replaces v1's globals

v1 kept per-scan state in module scope: a `template_definition` dict every
stage mutated, a fixed `~/.verinfast/temp_repo` clone path, a
`~/.verinfast_cache` database, and `os.chdir()` as control flow. A
`ScanContext` is created per scan, owns a unique temp work directory, and is
passed explicitly. Two scans can therefore share a process.

`scan_context()` removes the work directory in a `finally` — v1 only cleaned
up on the happy path.

## Scanner stays thin

`Agent` in v1 was 929 lines and did orchestration, git parsing, filesystem
walking, cloud dispatch and HTTP upload. This file decides what runs and
nothing else; each of those jobs belongs to another package.

## Never two traversals

`ScanContext.files_in` memoises a target's file list. `sizes` and `stats` both
need every file under a target, and walking a large monorepo twice is the same
waste `N12` exists to remove — it just moves the second traversal from inside
one scanner to between two. The list lives on the context because it is
per-scan derived state, which is what a context is for.

## Remote targets are cloned first

A target built from a served config's `repos:` list has a URL and no path.
Every scanner needs `ScanTarget.path`, so without `core/materialize.py` each
of the five skips it with "no local path" — five quiet skips per repository,
and a scan that uploads nothing while reporting no failure.

Clones go in the scan's work directory, removed on the way out. They are
**not shallow**: git history is one of the five artifacts and `--depth` would
silently truncate it; the `--since` window bounds the work instead.
Credentials are ambient, and a URL is never echoed into an error — it can
carry a token in its userinfo (`S5`).

## Scratch paths are derived, never concatenated

`ScanContext.scratch_for` sanitises `target.name` and disambiguates it with a
digest. The name is caller-controlled, so joining it to a path directly let
stats and findings scratch files land outside the workspace.

## What a result means

`_scan_target` records an outcome for **every** artifact in `REPO_ARTIFACTS`,
in upload order, so a partial scan is a prefix rather than an arbitrary
subset:

- **ok** — it ran and produced data.
- **skipped** — with a reason: disabled by config, no scanner ported yet, or
  nothing applicable (a code sample has no git history).
- **failed** — with an error. One scanner failing never aborts the others
  (`F19`), and the backstop around each `run()` reports rather than swallows.

"Found nothing" and "never ran" must never look alike (`F18`), which is why
there is no fourth state and no silent absence.

## Current state

`context.py` and `_scan_target` are implemented; `git`, `sizes` and `stats`
are wired through `scanners.base.registry()`. `_scan_cloud` still raises
`NotImplementedError` pending the provider registry.
