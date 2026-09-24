# core/ — Claude notes

- **No module-level mutable state, ever.** If a scanner needs to hand
  something to the report, it returns it in an `ArtifactResult`. v1's shared
  dict is why a multi-repo scan silently reported one repo (`D5`).
- **No `os.chdir()`.** Subprocesses take `cwd=`. Concurrency and re-entrancy
  both break on a process-global working directory (`L4`).
- **Never default a path into `~`.** Work, output and cache directories are
  injectable; unset means a per-scan temp directory, and in library mode with
  no `output_dir`, no files at all. An explicitly supplied `output_dir` is
  honoured wherever it points (`L7`, `S15`).
- **Report cleanup failures.** `scan_context` logs a work directory it could
  not remove rather than passing `ignore_errors=True` — the consequence is a
  clone left on someone else's disk (`N10`).
- **One target's failure must not abort the others** (`F19`). `_scan_target`
  collects failures into results; it does not let them propagate.
- **No bare `except:`.** v1 has a dozen; several hide real failures. Catch
  what you can name and record it on the result (`N10`).
- `Scanner.__init__` calls `config.for_library()` when `embedded` is set, so
  the caller cannot forget. Don't move that to the caller's side.
- `scan_path()` is the ATD v3 entry point: a directory with no git history and
  no remote. Skip git cleanly — never `git init` the tree (`S12`, `L8`).
- **Never join `target.name` to a path.** It is caller-controlled —
  `ScanTarget` is public and `scan_path(name=...)` takes what it is given —
  so `../..` or an absolute name escapes the workspace. Use
  `ScanContext.scratch_for`, which sanitises and disambiguates with a digest.
- **A remote target must be materialised before scanners see it.** Without
  it, a served config's `repos:` reaches every scanner as "no local path"
  and produces five quiet skips per repository — a scan that uploads nothing
  and reports no failure. `core/materialize.py` clones; a clone that fails
  is one clear failure per artifact, naming the cause.
- Every subprocess needs an explicit timeout; ATD runs this inside a
  request-serving worker (`L10`).
