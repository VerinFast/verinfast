---
title: Requirements: Embeddable Library API
parent: requirements
workstream: 5
tags: v2, requirements, api
---

# Requirements: Embeddable Library API

> *"Be importable as a Python module in ATD_v3 so it can run scans on demand
> against code samples."*

This is the requirement that forces the rewrite. Everything below is
**impossible** in v1.

## The five blockers in v1

| # | Blocker | Where |
|---|---|---|
| 1 | `Config.__init__` parses `sys.argv` unless `"pytest" in sys.argv[0]` | `config.py` |
| 2 | `Agent.__init__` calls `initial_prompt()`, which calls `input()` | `agent.py`, `user.py` |
| 3 | `os.chdir()` as control flow — in `parseRepo`, in three walkers, restored by assuming a module-level `curr_dir` | `agent.py`, walkers |
| 4 | Module-level mutable `template_definition` dict shared by every stage | `agent.py` |
| 5 | A single hardcoded clone path, `~/.verinfast/temp_repo`, and a single `~/.verinfast_cache` | `agent.py`, `code_scan.py` |

Plus: vendored-CLI calls (`semgrep.commands.scan`, `modernmetric.__main__.main`)
that raise `SystemExit`, and `exit(0)` in the preflight path.

## Requirements

- **L1 (MUST)** A public API importable with no side effects:
  ```python
  from verinfast import Scanner, ScanConfig, ScanResult
  result: ScanResult = Scanner(ScanConfig(...)).scan_path("/tmp/sample")
  ```
  Importing `verinfast` must not read argv, must not touch `~`, must not
  prompt, must not patch third-party libraries, and must not open a log file.
- **L2 (MUST)** Every scan returns a **typed result object** carrying the
  artifacts in memory. Writing to disk and uploading are separate, optional
  steps driven by the caller.
- **L3 (MUST)** No process-global state. Two `Scanner` instances must be able
  to scan two different trees concurrently in one process and produce correct,
  unmixed results.
- **L4 (MUST)** No `os.chdir()`. Every subprocess takes an explicit `cwd=`.
- **L5 (MUST)** No `input()`, no `print()`, no `exit()` anywhere reachable from
  the library API. Consent is a config field; progress is a callback; failure
  is an exception or a result field.
- **L6 (MUST)** No `SystemExit` escapes. Third-party CLIs run as subprocesses
  or behind adapters that convert exit codes to values.
- **L7 (MUST)** All filesystem locations injectable: work directory, output
  directory, cache directory, log destination. Default to a caller-supplied
  temp directory, never `~`.
- **L8 (MUST)** A **sample mode** for a bare directory of code with no git
  history and no remote: run Semgrep, sizes, stats and dependency parsing;
  skip git cleanly rather than synthesising a repo.
- **L9 (MUST)** Library mode is **network- and execution-restricted by
  default**: no telemetry POST, no package-manager installs, no consent files
  written to `~`. Each is an explicit opt-in. See
  [[Requirements: Security & Privacy]].
- **L10 (MUST)** Bounded resources: timeouts on every subprocess, a cap on
  tree size / file count, and cancellation that actually kills children.
  ATD v3 runs this inside a request-serving worker.
- **L11 (SHOULD)** Async-friendly. ATD v3's API is SQLAlchemy-async/FastAPI; a
  blocking call that holds the event loop for minutes is unusable. Either
  provide `async def` entry points or document `run_in_executor` explicitly.
- **L12 (SHOULD)** Scanners individually selectable, so ATD v3 can ask for
  "findings only" on a code sample without a git or cloud pass.
- **L13 (SHOULD)** A stable, versioned public surface (`__all__` + semver), so
  ATD v3 can pin it.

## Open design questions

Recorded in [[Open Questions]]: in-process vs. subprocess isolation for
untrusted samples, and whether `ScanResult` is pydantic (ATD's idiom) or
dataclasses (fewer dependencies).
