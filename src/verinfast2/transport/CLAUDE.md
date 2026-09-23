# transport/ — Claude notes

- **`paths.py` is a contract with another repository.** ATD v3 vendors a
  literal port and tests it against the same golden case. Never change a route
  string without the matching ATD change; a silent drift produces wrong URLs
  that still look plausible.
- **Keep it pure.** No HTTP, no config objects, no filesystem, no clock.
  `upload_path` is a function of its arguments. That is what makes the
  vendored port possible.
- **`logs` never takes the `uuid/` prefix; `agent_err` does.** Both sides test
  this. It looks like a bug and is not.
- **`utilization` is the route name; `instance_utilization` is the path
  segment.** Don't "fix" the mismatch.
- **Default `code_separator` is `/CodeScan`** as of VerinFast/verinfast#814.
  Servers still pin it explicitly because released agents predate that fix, so
  the override stays load-bearing.
- **Treat a non-200 as a failed upload.** ATD's ingest is 200-or-404 by
  design, and every route is replace- or upsert-shaped, so retry is safe —
  except **415** (ClamAV rejected the payload), which is never retryable.
  502 (AV unavailable) is.
- `oss`, `user_activity` and `load_balancers` have routes here that no scanner
  populates yet. That's deliberate.
- Adding a route: add it to `_routes()`, add it to `PER_REPO` if it needs a
  scan id, and add a case to `tests/v2/test_upload_paths.py`.
