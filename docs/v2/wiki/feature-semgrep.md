---
title: Feature: Security Scan (Semgrep)
parent: features
artifact: {repo}.findings.json
route: findings
tags: v2, feature, code
---

# Feature: Security Scan (Semgrep)

## What it produces

Native `semgrep --json` output for one repository: `results[]`, `errors[]`,
`paths`, `version`. Each result carries `check_id`, `path`, `start`/`end`
positions, and an `extra` block with `severity`, `fingerprint`, `lines`
(the matched snippet), `message`, `metavars` and a rule `metadata` blob
(`category`, `cwe`, `owasp`, `shortlink`, `technology`, `references`, ...).

Uploaded verbatim to `.../{repo}/findings`.

## How v1 does it

`src/verinfast/code_scan.py::run_scan`.

- Imports `semgrep.commands.scan` **directly** and calls `scan(custom_args)`
  in-process with `--config auto --json --output=<file> -q`, wrapped in
  `contextlib.redirect_stdout` and a `try/except SystemExit` — Semgrep's CLI
  exits the process on completion, so the exception *is* the return value.
- Skips entirely on Windows (Semgrep has never supported it).
- Consults [[Feature: Scan Caching]] first; a hit writes the cached JSON
  straight to the findings file and skips the scan.
- Post-processes through [[Feature: Privacy Controls]] truncation when enabled.
- Uploads even on a dry run, so the server's ingest can be exercised.

`--config auto` means **Semgrep fetches its rule registry over the network at
scan time**. Findings are therefore not reproducible across time, and the scan
requires outbound access to `semgrep.dev`.

## What v2 must keep

- The exact on-the-wire shape. ATD v3's `ingest_findings.py` models it with
  `extra="allow"` at every level, tolerates truncated strings, and
  delete-and-replaces per repository — so a retry is safe but a *shape* change
  is not.
- The `cwe`/`owasp`/`technology` string-or-array ambiguity: ATD normalises both,
  so v2 may keep emitting whatever Semgrep emits.
- Windows degradation must stay graceful, not fatal.

## What v2 must change

- **Do not import Semgrep's CLI internals.** Catching `SystemExit` from a
  vendored command module is a break-on-upgrade contract. v2 runs Semgrep as a
  subprocess with a pinned version, or uses a supported API if one exists by
  then. This matters much more in library mode, where a stray `SystemExit`
  would take down ATD v3's worker.
- **Make the rule source explicit.** `--config auto` should be the default but
  overridable (pinned ruleset / offline registry), and the resolved ruleset
  version should be recorded in the artifact so a finding set is explainable
  six months later.
- **Return findings, don't just write them.** See
  [[Requirements: Embeddable Library API]].

## Related

[[Feature: Privacy Controls]] · [[Feature: Scan Caching]] · [[ATD v3 Upload Contract]]
