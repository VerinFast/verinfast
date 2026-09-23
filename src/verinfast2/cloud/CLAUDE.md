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
