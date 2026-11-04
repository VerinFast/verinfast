# cloud/ — Claude notes

- **Return, don't raise** — same rule as `scanners/`. One artifact failing
  must not lose the other five, and "no credentials" must be distinguishable
  from "the API returned something we couldn't parse" (`F19`, `N10`).
- **No `shell=True` with interpolated values.** The v1 AWS cost command builds
  a shell string containing a config-supplied profile name (`D9`, `S9`).
  Related: `utils.std_exec` falls back to `check_output(cmd, shell=True)` with
  a *list*, which on POSIX silently runs only `cmd[0]`.
- **Use `boto3` for AWS**, not the CLI. It already ships.
- **Label the upload source correctly.** v1 reported Azure *and* GCP
  utilization uploads as coming from AWS (`D4`). Log-only, but it makes a
  cloud scan unreadable in the logs.
- **`user_activity` and `load_balancers` are new work, not a port.** Nothing
  in v1 produces them. Sources: CloudTrail / Azure sign-in + audit logs / GCP
  admin activity logs; and ELB-ALB-NLB / Azure LB + App Gateway / GCP
  forwarding rules (`F8`).
- The cloud envelope is fixed by ATD:
  `{"metadata": {"provider", "account"}, "data": [...]}`, upserted on
  `(report_id, provider, account, remote_id)`.
- v1 collected no GCP costs at all. If you add them, say so — it changes what
  a GCP report contains.
- The SDKs are moving behind extras (`[aws]`, `[azure]`, `[gcp]`), so don't
  import one at module scope in shared code.
- **Build results with `base.ok()` / `skipped()` / `failed()`**, not by hand.
  Three providers spelling "this didn't run" three ways is how `F18` erodes.
- **A skip carries a reason, always.** `not ported from v1 yet` for the four
  ported artifacts; something truthful for anything else. GCP costs must not
  say "not ported" — v1 never collected them.
- **Regional sweeps tolerate a refusing region and fail only when all of them
  refuse.** Opt-in regions return `AuthFailure` routinely. One region must not
  cost the inventory; every region failing must not read as an empty one.
- **Get regions from `session.get_available_regions(service)`**, not a literal
  list. v1's hardcoded list stopped covering new regions the day it was
  written, and it never said so.
- **`available()` answers, never raises.** `importlib.util.find_spec` raises
  when a *parent* package is absent (no `azure`, no `google` at all), which is
  the ordinary case — catch it. The orchestrator calls this before it can
  report anything, so a raise here loses all six artifacts.
- **The tests inject a session; they never reach a cloud.** `AwsProvider`
  takes a `session_factory` for exactly this. Note the suite is run both with
  and without the SDKs installed — CI installs `.[dev]` and has boto3, a lean
  dev venv does not — so never let a test's outcome depend on which.
