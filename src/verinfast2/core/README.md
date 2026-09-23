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

## Current state

`context.py` is implemented. `Scanner.scan()` and `scan_path()` are wired but
`_scan_target` / `_scan_cloud` raise `NotImplementedError` pending the scanner
and provider registries.
