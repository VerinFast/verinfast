---
title: Requirements: ATD v3 Integration
parent: requirements
workstream: 4
tags: v2, requirements, contract
---

# Requirements: ATD v3 Integration

ATD v3 is `VerinFast/good-place` → `services/atd`. It is the consumer, and its
contract is already pinned by tests on its side. **v2 conforms; it does not
negotiate.**

## Requirements

- **A1 (MUST)** Every upload path v2 produces must match
  [[ATD v3 Upload Contract]] byte for byte, including the "logs never gets the
  uuid prefix" exception.
- **A2 (MUST)** Uploads carry **no `Authorization` header**. The report
  UUID in the URL is the credential. ATD's routes are unauthenticated by
  design and 404 on an unknown report or scan session.
- **A3 (MUST)** Mint a scan session first: `GET {prefix}{report}{code_sep}`
  returns an opaque scan id used in every per-repo path that follows.
- **A4 (MUST)** Default `code_separator` to `/CodeScan` — already true on
  `main` since PR #814 (`4ae508b`) — and keep honouring a server-supplied
  override. ATD pins it in every served config because agents already in the
  field predate that fix.
- **A5 (MUST)** Support both addressing modes — `uuid/`-prefixed and the
  deprecated legacy integer id — since ATD keeps both route families.
- **A6 (MUST)** Keep the payload shapes ATD parses: numstat strings including
  `"-"`, the `"."` root entry in sizes, modernmetric's
  `overall` / `stats.<agg>.<prop>` blocks, native Semgrep JSON, the flat
  dependency array, and the `{"metadata": {...}, "data": [...]}` cloud
  envelope.
- **A7 (MUST)** Consume the served agent config
  (`GET /api/agent/config/{uuid}/VerinFastConfig.yaml`) without modification,
  including its optional `?scan=code|cloud` filter.
- **A8 (MUST)** Treat any non-200 as a failed upload and retry, since ATD's
  routes are deliberately 200-or-404 and every ingest is
  replace/upsert-shaped.
- **A9 (SHOULD)** Emit the two artifacts ATD is waiting on — `user_activity`
  and `load_balancers` — completing the cloud widget set.
- **A10 (SHOULD)** Keep `tests/test_dry.py`'s golden path assertion, which ATD
  vendors verbatim as its drift canary
  (`make_upload_path(uuid_config, "scan_id", report="9a6e…") ==
  "/report/uuid/9a6e…/CodeScan"`).

## In-process integration

Beyond the HTTP contract, ATD v3 needs to `import verinfast`
([[Requirements: Embeddable Library API]]). Two integration shapes to design
for:

1. **Agent-driven** (today): the customer runs the CLI, which fetches its
   config from ATD and POSTs results back.
2. **Server-driven** (new): ATD v3 calls the library directly against a code
   sample it already has, and persists the returned `ScanResult` through its
   own ingest services rather than over HTTP.

Shape 2 must not require a report UUID, a base URL, or any upload at all.

## Environment notes

- ATD's `agent_ingest_base_url` already includes the `/api` mount, so the
  agent's `baseurl` + `prefix` concatenation lands correctly with no extra
  segment.
- ATD ClamAV-scans and archives every raw payload it receives; an infected body
  is rejected with **415** and an AV outage with **502**. v2's retry policy
  must not treat 415 as retryable.
