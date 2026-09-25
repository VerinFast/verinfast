# transport/

Getting results to the server.

| File | What |
| ---- | ---- |
| `paths.py` | **The ATD v3 wire contract.** Pure URL construction, no I/O. |
| `client.py` | `Uploader` — the HTTP half: retry, status semantics, multipart. |
| `payloads.py` | Findings truncation and the cloud envelope. Pure functions. |

## paths.py is a published interface

ATD v3 keeps a literal port of this module in its own
`tests/e2e/upload_paths.py` and asserts the two agree on a golden case:

```python
upload_path(UploadConfig(uuid=True), "scan_id", report="9a6e…")
# "/report/uuid/9a6e…/CodeScan"
```

`tests/v2/test_upload_paths.py` pins the same case from this side. A change
here needs the matching change on the ATD side — treat it like a schema
migration, not an implementation detail.

## The shape

`{prefix}{uuid/}{report}{code_separator}/{scan_id}/{repo}/{artifact}`

- `prefix` defaults to `/report/`
- `code_separator` defaults to `/CodeScan`
- `uuid/` appears for uuid-addressed reports — **except on `logs`**, which is
  a deliberate asymmetry tested on both sides
- the deprecated integer-id route family is still supported

## Authentication

There is none. The report UUID in the URL *is* the credential; ATD's ingest
routes take no `Authorization` header and 404 on an unknown report or scan
session, so a probe can't tell "missing" from "forbidden".

## Status semantics

`client.py` decides retry from ATD's documented codes, not from guesswork:

| Code | Meaning | Retry? |
| ---- | ------- | ------ |
| 200 | accepted | — |
| 404 | unknown report or scan session | no |
| 415 | antivirus rejected the payload | **never** |
| 422 | payload shape rejected — an agent bug | no |
| 502 | antivirus unavailable | yes |
| 5xx | server-side failure | yes |

415 is the one that matters: ClamAV rejecting a payload is a verdict about
the bytes, so resending them fails identically and burns the scan's time
budget. Retrying at all is safe only because every ingest route is
idempotent — `findings` and `dependencies` delete-and-replace, the rest
upsert on a natural key.

`is_retryable()` takes the **whole 500–599 range**, not a hand-listed subset:
listing them by hand meant a 501 or 507 was given up on after one attempt
despite the rule above saying otherwise.

## Uploads disabled must cost nothing

`should_upload: false` and `dry: true` make every call a no-op success
(`F17`). That means `enabled` is checked *first* — before a `scan_id` is
demanded, before a log file is opened. Checking the session first turned
every artifact in a dry run into a failed upload, and `mint_scan_session`
decoded a body it had never fetched.

**An upload never raises.** Every call returns an `UploadResult`. A scan that
produced five good artifacts and failed to upload one reports exactly that.
That covers a payload that will not serialise, not only a transport failure:
`json.dumps` runs inside the contract, and what it rejects comes back as a
`permanent` result — non-retryable, because there are no bytes to resend.

## Truncation is the privacy boundary

`payloads.truncate_findings` cuts `extra.lines` — the matched source — while
preserving the keys in `NO_TRUNCATE` (rule ids, CWE, OWASP, path, message).
It returns a new object; v1 mutated in place, which is why the same findings
could not be both uploaded and rendered locally.

**It is applied by the uploader, in `_shape`.** The findings scanner returns
full source on purpose, because the local HTML report needs it — so cutting
it is a property of *leaving the machine*. Leaving that to the caller meant
`privacy.truncate_findings` defaulted to on and was enforced nowhere, which
is the worst shape a privacy control can take. Use `Uploader.for_config` and
the setting cannot be lost on the way.

## Importing this package does not import httpx

`client.py` is behind a lazy `__getattr__`. `from verinfast2.transport import
Uploader` still works, but `paths.py` stays dependency-free — which is what
makes ATD's vendored copy of it possible. `tests/v2/test_public_api.py` pins
this.

## Current state

Implemented and covered by 168 tests, all offline. `tests/v2/test_atd_contract.py`
replays ATD's own fixture payloads through `Uploader` against an
`httpx.MockTransport`, asserting the paths ATD's test asserts.
