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
  502 (AV unavailable) is. `is_retryable()` takes the whole 500–599 range —
  a hand-written set meant a 501 or 507 was given up on after one attempt
  despite the documented rule. 415 lives in `NEVER_RETRY` and a test asserts
  it directly, because adding it would look like a reasonable generalisation
  and would be wrong.
- **Check `enabled` before anything else in a public method.** A dry run
  mints nothing, so demanding a `scan_id` first turned every artifact into a
  failed upload, and `mint_scan_session` tried to decode a body it never
  fetched. `should_upload: false` has to cost nothing (`F17`); there are
  tests for the whole sequence.
- **Truncation happens here, in `_shape`, not at the call site.** The
  findings scanner returns full source on purpose and
  `privacy.truncate_findings` defaults to on — leaving the cut to whoever
  wires the CLI meant a privacy control that was on by default and enforced
  nowhere (`S2`). Build uploaders with `Uploader.for_config` so the setting
  cannot be dropped on the way.
- **Never import `client` eagerly from `__init__.py`.** It needs httpx, and
  `config/schema.py` imports `paths` through this package — so an eager
  import puts an HTTP stack behind `from verinfast2 import ScanConfig`, and
  behind the module ATD copies verbatim. The lazy `__getattr__` is
  load-bearing and there is a test for it.
- **An upload never raises.** Failures come back as `UploadResult`, including
  a payload `json.dumps` rejects — serialisation is inside the contract, and
  its result is `permanent=True` so nothing retries it. The one exception is a
  bad route name, which is a caller bug and raises from `paths` before any
  request — don't "helpfully" catch it.
- **The report UUID is the credential.** Anything bound for a log goes
  through `_redact` first; agent logs themselves get uploaded.
- **Truncation lives in `payloads.py`, not in the findings scanner.** The
  scanner's job is to find things; the local HTML report wants the full text.
  Cutting happens on the way out.
- **`NO_TRUNCATE` is v1's exclusion list unchanged.** Widening it is a
  data-comparability decision about two years of stored findings, not a
  refactor.
- `oss`, `user_activity` and `load_balancers` have routes here that no scanner
  populates yet. That's deliberate.
- Adding a route: add it to `_routes()`, add it to `PER_REPO` if it needs a
  scan id, and add a case to `tests/v2/test_upload_paths.py`.
