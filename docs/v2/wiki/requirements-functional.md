---
title: Requirements: Functional
parent: requirements
tags: v2, requirements
---

# Requirements: Functional

## Scan targets

- **F1 (MUST)** Scan a **remote git repository** by URL, with optional
  `@branch` suffix, over SSH or HTTPS, including URLs carrying credentials.
- **F2 (MUST)** Scan a **local directory**, with optional `@branch`, whether or
  not it is a git repository — and **without modifying it**. No `git init`, no
  checkout of a different branch unless explicitly asked.
- **F3 (MUST)** Scan multiple repositories in one run, keeping per-repository
  artifacts distinct end to end (including in the local HTML report, which v1
  gets wrong).
- **F4 (MUST)** Scan one or more cloud accounts across AWS, Azure and GCP.
- **F5 (SHOULD)** Scan an **in-memory or temporary code sample** with no git
  history and no remote — the ATD v3 case. See
  [[Requirements: Embeddable Library API]].

## Artifacts

- **F6 (MUST)** Produce, per repository: git history, file sizes/inventory,
  modernmetric statistics, Semgrep findings, dependency inventory — in the wire
  shapes recorded in [[ATD v3 Upload Contract]].
- **F7 (MUST)** Produce, per cloud account: costs, instances, utilization,
  block storage.
- **F8 (MUST)** Produce cloud **user-activity** and **load-balancer**
  inventories. ATD v3 has shipped ingest, models, migrations and widgets-in-
  waiting for both; they are blocked only on this agent. New in v2.
- **F9 (SHOULD)** Produce host system info, and decide whether to upload it
  ([[Open Questions]]).
- **F10 (MAY)** Produce the OSS-embeddings payload ATD's `/oss` route accepts.
  Today that producer is a separate pipeline; folding it in is optional.

## Configuration

- **F11 (MUST)** Accept configuration from a local YAML file, a remote YAML
  URL, a Python dict/dataclass, or CLI flags, with a documented precedence
  order.
- **F12 (MUST)** Honour `modules.code.git.start` — currently dropped by a typo.
- **F13 (MUST)** Honour every documented module toggle, including `run_sizes`,
  which is currently inert.
- **F14 (MUST)** Honour `server.prefix`, `server.code_separator` and
  `server.cost_separator`, and default `code_separator` to `/CodeScan`.
- **F15 (MUST)** Support `should_upload: false` + `--output` for offline
  inspection before anything is sent.

## Output

- **F16 (MUST)** Write every artifact to an output directory as JSON, in
  addition to (not instead of) uploading.
- **F17 (MUST)** Render a local HTML report covering **all** scanned
  repositories, working without network access.
- **F18 (SHOULD)** Emit a machine-readable run summary (what ran, what was
  skipped, what failed, what was uploaded) so ATD v3 can distinguish "clean
  scan, no findings" from "the scan never ran".

## Behaviour

- **F19 (MUST)** A failure scanning one repository or one cloud account must
  not abort the remaining targets, and must be reported rather than swallowed.
- **F20 (MUST)** Uploads must be idempotent-safe: ATD v3 delete-and-replaces or
  upserts on every route, so a retry is correct. v2 SHOULD therefore retry
  transient failures.
- **F21 (SHOULD)** Support concurrent scanning of independent repositories.
  Impossible in v1 — one fixed `temp_repo` path, one global dict, `os.chdir`.
