---
title: Feature: Configuration & CLI
parent: features
entrypoint: verinfast = verinfast.agent:main
tags: v2, feature, plumbing
---

# Feature: Configuration & CLI

## Config sources, in precedence order

1. **A YAML file** — `.verinfast.yaml` by default, searched in the current
   directory and then every ancestor until `/`.
2. **A remote YAML file** — if `--config` starts with `http://` or `https://`,
   it is downloaded to a random `<uuid4>.yaml` in the CWD, parsed, and
   (supposedly) deleted after. ATD v3 serves exactly this at
   `GET /api/agent/config/{report_uuid}/VerinFastConfig.yaml`.
3. **Command-line arguments**, which overwrite whatever the file said.

Keys the file may set: `baseurl`, `should_upload`, `dry`, `delete_temp`,
`truncate_findings`, `truncate_findings_length`, `server.{prefix,code_separator,cost_separator}`,
`report.{uuid,id}`, `modules.code.{run_git,run_scan,run_sizes,run_stats,dependencies,git.start}`,
`modules.cloud[]`, `repos[]`, `local_repos[]`.

Flags: `-c/--config`, `-o/--output`, `-t/--truncate`, `-d/--dry`,
`--should_upload`, `--base_url`, `--uuid`, `--path`, `-g/--should_git`,
`-v/--version`.

## Default behaviour

With no repos, no local_repos and no cloud module configured, the agent scans
`./` as a single local repo and turns `runGit` **off**.

## Defects

- **`Config.__init__` parses `sys.argv`** unless `"pytest" in sys.argv[0]`.
  That string check is the only thing separating library use from CLI use, and
  it fails for anything that is not pytest — including ATD v3. This is the
  hardest blocker on [[Requirements: Embeddable Library API]].
- **`modules.code.git.start` is dropped.** `handle_config_file` does
  `g = ["git"]` instead of `g = c["git"]`, then tests `if "start" in g` against
  that literal list. The configured window never applies.
- **`run_sizes` is dead.** `self.runSizes` is set from config and reported to
  telemetry, but nothing reads it — the sizes walk always runs.
- **Dates are not ISO.** `default_start` is built with f-strings from
  `date.year/month/day`, producing `2026-3-1` rather than `2026-03-01`.
- **The remote config is not reliably deleted.** `delete_config_after` is set
  to `True` and never acted on; the downloaded `<uuid>.yaml` — which contains
  the report UUID, i.e. the upload credential — is left in the working
  directory.
- Class-level mutable defaults on `Config` (`output_dir`, `log_file`) are
  evaluated at import time, so the log filename timestamp is "when the module
  was imported", not "when the scan started". `__init__` recomputes `log_file`
  but not `output_dir`.
- `config.config` is initialised to the `FileNotFoundError` **class** as a
  sentinel.

## What v2 must keep

- Remote-config fetch. ATD v3's whole onboarding flow depends on
  `verinfast -c https://.../VerinFastConfig.yaml`.
- The YAML key names, unchanged — ATD v3's `services/code_scan.py` emits them.
- `server.code_separator` honouring. ATD pins `/CodeScan`; v1 defaults to the
  old product name. See [[ATD v3 Upload Contract]].

## What v2 must change

- Config is a **typed, validated object constructed from an explicit source**
  (dict, file path, or URL). Argv parsing lives in the CLI layer only.
- Never write the fetched config to the CWD; parse it in memory or into a
  temp file that is removed in a `finally`.

## Related

[[Requirements: Embeddable Library API]] · [[Known Defects & Debt]]
