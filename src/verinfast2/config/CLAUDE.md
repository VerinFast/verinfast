# config/ — Claude notes

- **Never read `sys.argv`, an environment variable or a file at import, or in
  a `ScanConfig` constructor.** Loaders are explicit calls. This is `L1`, and
  `tests/v2/test_public_api.py` enforces it.
- **The YAML key names belong to ATD.** `should_upload`, `dry`,
  `modules.code.git.start`, `modules.cloud[]`, `repos`, `local_repos`,
  `server.code_separator` — ATD's `services/code_scan.py` emits exactly these.
  Renaming one breaks the served-config path (`A7`).
- **`modules.code.git.start` must actually apply.** v1 wrote `g = ["git"]`
  where it meant `g = c["git"]`, so the configured window never reached
  `GitModule.start` and every scan used the default (`D1`). ATD documents this
  as a known agent quirk — fixing it is the point.
- **`run_sizes` has to gate something.** v1 parsed it, reported it to
  telemetry, and never read it (`D2`).
- **Never write the fetched remote config to disk.** It carries the report
  UUID, which is the upload credential. v1 saved it to the working directory
  and never deleted it despite setting `delete_config_after` (`D6`, `S5`).
- Dates are `datetime.date`, not f-string-built text. v1 emitted `2026-3-1`.
- **A malformed value from ATD costs that setting, not the scan.** `_as_date`
  returns `None` on junk and the default applies. A served config is another
  team's deploy landing in the field, so failing the whole run on one bad key
  is the wrong trade — but only for keys ATD owns. Our own `ScanConfig` stays
  `extra="forbid"`.
- **Cloud account ids are coerced to `str`.** An unquoted YAML id arrives as
  an int and stops matching ATD's `(report, provider, account, remote_id)`
  upsert key — the rows land, under the wrong account.
- **`repos` absent and `repos: []` are not the same thing.** ATD only emits
  the key when non-empty, because an explicit empty list suppresses the
  scan-the-working-directory fallback. Don't normalise them together.
- Changing a default here changes behaviour for every existing config file.
  Say so in the PR body.
