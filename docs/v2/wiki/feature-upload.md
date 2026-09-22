---
title: Feature: Upload & Report Addressing
parent: features
module: src/verinfast/upload.py
tags: v2, feature, plumbing, contract
---

# Feature: Upload & Report Addressing

## The mechanism

`Uploader.make_upload_path(path_type, report, code, repo_name)` builds every
URL the agent posts to, from three configurable pieces:

- `prefix` — default `/report/`
- `code_separator` — the segment between report id and scan id
- `cost_separator` — default empty
- `uuid` — whether to insert a `uuid/` segment

Then `Agent.upload()` POSTs the file: JSON bodies with
`Content-Type: application/json`, log files as multipart under the field name
`logFile`. **No `Authorization` header is ever sent** — the report UUID in the
URL is the secret.

A non-200 is logged and the upload is considered failed; the agent does not
retry. On success it opportunistically uploads a sibling `.err` file, if one
exists, to `err_<route>`.

## The one deliberate quirk

`logs` never gets the `uuid/` prefix, even when the report is addressed by
UUID. Everything else does. ATD v3 has a dedicated test for this.

## Route table

See [[ATD v3 Upload Contract]] for the full path list and the server's
expectations.

## Defects

- `self.scanId` is only assigned when `shouldUpload` is true. Every code path
  that reads it is behind the same flag, so it works — but it is an attribute
  that may or may not exist depending on config, and `make_upload_path` raises
  if it is missing.
- The default `code_separator` is the **old product name**, not `/CodeScan`.
  ATD v3 works around this by pinning `server.code_separator` in every served
  config. v2 should default to `/CodeScan` and keep honouring the override.
- Uploads are sequential, unretried and unthrottled. A large scan uploads a
  dozen files one at a time and gives up on the first 500.
- `upload()` returns `True` for "skipped because uploads are off", which makes
  "did it upload" unanswerable from the return value.

## What v2 must change

- Make the path builder a **pure function with an exhaustive route enum**, kept
  in one file, so ATD's vendored copy can stay a literal port.
- Add bounded retry with backoff on 5xx/connection errors.
- Distinguish skipped / succeeded / failed in the return type.

## Related

[[ATD v3 Upload Contract]] · [[Feature: Privacy Controls]]
