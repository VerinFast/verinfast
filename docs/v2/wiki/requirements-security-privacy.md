---
title: Requirements: Security & Privacy
parent: requirements
tags: v2, requirements, security, privacy
---

# Requirements: Security & Privacy

## Threat model

Three parties, three concerns:

| Party | Concern |
|---|---|
| The scanned company | Their code and credentials must not leave. |
| The person running the agent | The agent must not damage or exfiltrate from their machine. |
| ATD v3 / VerinFast | A scanned repository is **untrusted input** and must not achieve code execution in the platform. |

The third is new. v1 only ever ran on the customer's machine; v2 runs inside
our own service.

## Requirements

### Data egress

- **S1 (MUST)** Never upload source files, credentials, environment variables
  or config contents.
- **S2 (MUST)** Keep finding-snippet truncation, with ATD's defaults (on, 30
  chars) honoured from the served config.
- **S3 (MUST)** Document every outbound network destination in the README:
  the configured `baseurl`, the Semgrep rule registry, PyPI/npm/NuGet/
  RubyGems metadata lookups, and the telemetry endpoint.
- **S4 (MUST)** Make the `logger.verinfast.com` telemetry POST documented,
  consent-covered and disableable. Today `utils/license.py` sends
  `{baseurl, ran_*, uuid, product, version}` on every run that has a report id
  or uploads enabled; it is in neither the README nor the consent prompt.
- **S5 (MUST)** Never leave the downloaded remote config — which contains the
  report UUID, the upload credential — on disk. `delete_config_after` is set
  today and never honoured.
- **S6 (SHOULD)** Redact repo URLs (which may embed credentials), absolute
  paths and cloud account ids from uploaded logs.

### Code execution

- **S7 (MUST)** Package-manager execution (`npm install`, `composer install`,
  `gem install`) becomes an **explicit opt-in**, defaulting to off, and is
  **refused outright in library mode**. Today it is unconditional whenever a
  matching manifest is found.
- **S8 (MUST)** Prefer lockfile parsing over installation everywhere a
  lockfile exists.
- **S9 (MUST)** No `shell=True` with interpolated, externally-supplied values.
  Present today in the git log command (branch name, start date) and the AWS
  cost command (profile name). Related: `utils.std_exec` falls back to
  `subprocess.check_output(cmd, shell=True)` **with a list argument**, which on
  POSIX runs only `cmd[0]` and silently discards the rest.
- **S10 (MUST)** Every subprocess gets an explicit `cwd`, an explicit timeout,
  and a bounded output buffer.
- **S11 (SHOULD)** For untrusted samples, support running the scan in an
  isolated child process so a scanner crash or a hostile file cannot take down
  ATD's worker. See [[Open Questions]].

### Filesystem

- **S12 (MUST)** Never modify the scan target. No `git init`, no branch
  checkout on a local path unless explicitly requested.
- **S13 (MUST)** Never follow symlinks out of the scan root.
- **S14 (MUST)** Clone into a caller-supplied or per-scan unique directory,
  not the fixed `~/.verinfast/temp_repo`, and clean up in a `finally`.
- **S15 (MUST)** In library mode, write nothing to `~` — not the cache, not
  `preferences.yaml`, not logs.

### Supply chain

- **S16 (MUST)** Pin or floor every dependency with a rationale, and record its
  license in [[Dependency & License Review]].
- **S17 (MUST)** Keep the agent's own dependency surface small enough to audit.
  Today it pulls the entire Azure, AWS and GCP SDK families plus Semgrep,
  johnnydep and modernmetric.
- **S18 (SHOULD)** Reproducible scans: record the resolved Semgrep ruleset
  version in the findings artifact, since `--config auto` is a moving target.
