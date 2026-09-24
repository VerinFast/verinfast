# scanners/ — Claude notes

- **Return, don't raise.** A failure is an `ArtifactResult` with
  `Outcome.FAILED` and an error string. Raising loses the other artifacts
  (`F19`).
- **Never modify the scanned tree.** No `git init`, no branch checkout on a
  local path unless explicitly asked. v1 created `.git` directories in users'
  folders (`D3`, `S12`).
- **Never `os.chdir()`.** `cwd=` on the subprocess (`L4`).
- **Never call another tool's `__main__.main()` or import its CLI.** Semgrep
  and modernmetric both exit the process on completion, so the "return value"
  is a `SystemExit` — which lands in ATD v3's worker (`D18`, `L6`).
- **`--config auto` is not allowed.** It fetches rules whose licence permits
  internal, non-competing, non-SaaS use only, and it makes scans
  irreproducible. Pin a ruleset and record its version in the artifact
  (`S18`). A test asserts the string never appears in the argv. The
  reasoning is on *Semgrep Alternatives* in the v2 design wiki, which is
  kept locally in Waikiki and deliberately **not** in this repository — do
  not "restore" it here.
- **Scan `.` with `cwd=` the target, never an absolute path.** The engine
  copies the path it was given into every finding, so an absolute one puts
  the scanning machine's directory layout into ATD (`S3`).
- **Exit 1 means findings were found, not that the engine failed.** Only
  codes outside `RAN` are errors.
- **Never truncate findings in the scanner.** That is the upload boundary's
  job (`transport/payloads.py`); the local HTML report wants the full text
  and the same object serves both.
- **A missing engine is a FAILED result, not a skip.** Findings were asked
  for and there are none — that must not look like a clean scan (`F18`).
- **Package-manager execution is opt-in and refused when `embedded`.**
  `npm install` / `composer install` / `gem install` run arbitrary code from
  the scanned project's dependency graph (`S7`).
- **The wire shapes are fixed by ATD**, not by us: numstat values stay strings
  including `"-"`; sizes keeps its `"."` root entry and four metadata keys;
  stats keeps `overall` and `stats.<agg>.<prop>`; dependencies stays a flat
  array with `name` and `source` required. Changing one needs the matching
  change on the ATD side.
- **Never pass a bare `YYYY-MM-DD` to `git --since`.** git's approxidate
  fills in the current time of day, so the window silently depends on when
  the scan ran. `since_argument` pins midnight, and there is a test.
- **`sizes` and `stats` paths are both `./`-prefixed, and must stay that
  way.** ATD merges `ReportCodeFile` by path and rewrites modernmetric paths
  to `./…`; if the two artifacts disagree, ATD stores two rows per file and
  every per-file join halves. There is a test asserting they agree.
- **Get the file list from `ctx.files_in`, never by walking again.** The
  context memoises it per target so the tree is walked once per scan.
- **modernmetric runs via its CONSOLE SCRIPT, never `python -m`.** This is
  not a style preference and reverting it silently breaks macOS. modernmetric
  submits `process_file` to a `multiprocessing.Pool`, and a function pickles
  by `__module__` + `__qualname__`. Under `python -m modernmetric` that
  module is `"__main__"`, which in a **spawned** child is the `-m` launcher —
  so the child raises `AttributeError`, the parent's `async_result.get()`
  times out, and `__main__.py` drops the file with a bare `continue`. Every
  file. **Exit code 0, empty `files` map**, `files × file_timeout` seconds
  spent. `fork` hides it; macOS defaults to `spawn`. `resolve_tool()` looks
  beside `sys.executable` first, then `PATH`, and only then falls back to
  `-m`.
- **`_check_coverage` is load-bearing.** A run that analysed none of the
  files it was given is a FAILED artifact, not an empty one — that is `F18`
  applied to a third-party tool that fails silently by design. Never relax it
  to make a platform pass.
- **modernmetric's cache goes in the scan's work directory, absolute.** It
  builds its path as `Path(Path.home(), cache_dir, cache_db)`, and pathlib
  discards everything left of an absolute component — an absolute
  `--cache-dir` is the only way to stop it writing SQLite into the user's
  home (`L7`, `S15`).
- **Never an in-process import of another tool's `__main__`** (`D18`, `L6`).
- **The `"."` root entry's size includes `.git`; `metadata.real_size` does
  not.** ATD lifts the root entry onto `repository.file_size`, so changing
  what that number means breaks every historical comparison.
- **A missing scanner is a skip with a reason, not an absent artifact.**
  `registry()` returning nothing for an artifact is expected during the port;
  the orchestrator records it. Never let "found nothing" and "never ran" look
  alike (`F18`).
- Adding a scanner: implement the protocol, register it in `base.registry()`,
  add its artifact to `models.Artifact`, and confirm it has an upload route.
