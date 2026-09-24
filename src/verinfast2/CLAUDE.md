# verinfast2/ — Claude notes

- **This package is not shipped yet.** `pyproject.toml` pins the wheel to
  `src/verinfast/`. Don't "fix" that until cutover is the actual task.
- **Never reintroduce an import-time side effect.** No argv parsing, no
  `input()`, no `~` access, no `patch_pygments()`-style monkeypatching, no log
  file. `tests/v2/test_public_api.py` enforces this in a subprocess with
  hostile argv — if you make it fail, you broke the reason v2 exists.
- **No module-level mutable state.** v1's `template_definition` dict is why a
  multi-repo scan showed one repo and why two scans can't share a process.
  Per-scan state belongs on `ScanContext`.
- **No `os.chdir()`.** Pass `cwd=` to subprocesses. Three v1 walkers chdir and
  one failure leaves the process in the wrong directory.
- **Nothing in `core/`, `scanners/` or `cloud/` may print, prompt or exit.**
  Progress is the `ScanContext.progress` callback; failure is a returned
  `ArtifactResult` or an exception. Only `cli/` talks to a human.
- **Requirement ids are real.** `L1`, `S7`, `D23` and friends resolve to pages
  in the VerinFast v2 wiki, which is kept locally in Waikiki and is
  deliberately **not** in this repository. Cite the ids; don't invent new
  ones, and don't add the wiki (or a copy of it) here.
- Files stay under 500 lines. Split rather than grow.
- Every folder has a `README.md` and a `CLAUDE.md`, and they must say the same
  things — same edit, same PR.
