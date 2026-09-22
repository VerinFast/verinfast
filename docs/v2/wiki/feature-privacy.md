---
title: Feature: Privacy Controls
parent: features
tags: v2, feature, privacy, security
---

# Feature: Privacy Controls

Privacy is the product. A customer runs VerinFast precisely because they will
not hand over the code.

## What exists today

### Finding truncation

`truncate_findings` (bool) + `truncate_findings_length` (int, default 30) cap
the length of **every nested string** in the Semgrep payload, except an
allowlist of keys that are metadata rather than code:

```
cwe, owasp, path, check_id, license, fingerprint,
message, references, url, source, severity
```

Implemented in `utils.truncate_children`. ATD v3's configs default it **on**,
and its ingest route is explicitly documented as tolerating truncated strings.
A negative `--truncate` value disables it.

### What never leaves

Source files, credentials, cloud keys, and the contents of the local config are
never uploaded. The closest thing to code on the wire is the Semgrep `lines`
snippet, which truncation caps.

### Consent prompts

`user.py::initial_prompt()` asks, once, whether diagnostic logs may be uploaded
to StartupOS, and explains that preferences live in `~/.verinfast/`. The answer
is persisted to `~/.verinfast/preferences.yaml`.

### Local inspection

`should_upload: false` plus `--output=<dir>` lets a customer read everything
before any of it is sent. This is a documented selling point and must survive.

## What needs attention in v2

- **`utils/license.py` phones home on every run.** When `reportId != 0` or
  uploads are on, it POSTs `{baseurl, ran_dependencies, ran_git, ran_scan,
  ran_sizes, ran_stats, uuid, product, version}` to
  `https://logger.verinfast.com/logger`. The docstring frames it as detecting
  malicious redistribution. It is not mentioned in the README, not covered by
  the consent prompt (which is about *log* upload), and not disableable. In v2
  it must be documented, covered by consent, and switchable — and **off by
  default in library mode**, where there is no human to consent.
- **The consent prompt is `input()` inside `Agent.__init__`.** A library cannot
  prompt. See [[Requirements: Embeddable Library API]].
- **The downloaded remote config is left on disk.** It contains the report
  UUID, which is the upload credential. See [[Feature: Configuration & CLI]].
- **Logs are uploaded wholesale.** `main()` uploads every `*log.txt` in the
  output directory; those logs contain repo URLs, paths, and cloud account ids.
  Worth a truncation/redaction pass of its own.
- **Truncation is opt-in.** Given the threat model, consider defaulting it on,
  matching what ATD v3 already configures.

## Related

[[Requirements: Security & Privacy]] · [[Feature: Upload & Report Addressing]]
