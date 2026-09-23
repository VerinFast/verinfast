# transport/

Getting results to the server.

| File | What |
| ---- | ---- |
| `paths.py` | **The ATD v3 wire contract.** Pure URL construction, no I/O. |

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

## Current state

`paths.py` is implemented and covered by 44 tests. HTTP and retry are not
written yet.
