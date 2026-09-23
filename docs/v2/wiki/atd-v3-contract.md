---
title: ATD v3 Upload Contract
parent: verinfast-v2
source: good-place@74e41ff services/atd/api
tags: v2, contract, api
---

# ATD v3 Upload Contract

Everything here was read from `VerinFast/good-place@74e41ff`,
`services/atd/api/atd_api/routes/`. ATD's own
`tests/e2e/test_agent_contract.py` walks this whole table against a vendored,
literal port of `verinfast/upload.py::make_upload_path`.

All paths are relative to `baseurl`, which already includes ATD's `/api` mount.
`{prefix}` defaults to `/report/`; `{code_sep}` must be `/CodeScan`.

## 1. Mint a scan session

| Method | Path | Returns |
|---|---|---|
| GET | `/report/uuid/{uuid}/CodeScan` | opaque scan id (string) |
| GET | `/report/{id}/CodeScan` | same, legacy int-id addressing |

The returned id becomes `{scanId}` below. v1 strips surrounding quotes from
the response body.

## 2. Per-repository artifacts

`POST /report/uuid/{uuid}/CodeScan/{scanId}/{repo}/<artifact>`
(plus a deprecated `/report/{id}/…` twin for each).

| Artifact | Body | Server behaviour |
|---|---|---|
| `git` | array of commit objects | upsert on `(repository_id, hash)`; deltas replaced |
| `sizes` | `{files:{…}, metadata:{…}}` | merge-by-path upsert; `"."` → `repository.file_size` |
| `stats` | modernmetric JSON | merge-by-path; `overall.*` → repository; `stats.<agg>.<prop>` flattened; unknown keys dropped |
| `findings` | native `semgrep --json` | **delete-and-replace** all rows for the repo |
| `dependencies` | flat array of entries | **delete-and-replace**; sets `dependencies_ran` |
| `oss` | embedding files | exists, but today's producer is a separate pipeline |

`{repo}` keeps its `.git` suffix for cloned remotes and is the directory
basename for local scans. It is an opaque string to ATD.

## 3. Cloud artifacts

`POST /report/uuid/{uuid}/<artifact>` (plus deprecated `/report/{id}/…`).

Shared envelope: `{"metadata": {"provider": "aws|azure|gcp", "account": "<id>"}, "data": [...]}`

| Artifact | Path segment | Status |
|---|---|---|
| Costs | `costs` | agent produces it |
| Instances | `instances` | agent produces it |
| Utilization | `instance_utilization` | agent produces it |
| Block storage | `storage` | agent produces it |
| User activity | `user_activity` | **ingest ready, agent does not produce it** |
| Load balancers | `load_balancers` | **ingest ready, agent does not produce it** |

Upsert key: `(report_id, provider, account, remote_id)`.

## 4. Logs and error files — multipart, field name `logFile`

| Path | Note |
|---|---|
| `POST /report/{report}/agent_logs` | **no `uuid/` segment**, even for a uuid-addressed report |
| `POST /report/uuid/{uuid}/agent_logs` | also accepted |
| `POST /report/uuid/{uuid}/agent_err/{stats_err\|findings_err}` | **with** the uuid prefix |

The asymmetry is deliberate on both sides and has its own test.

## 5. Agent config

| Method | Path | Auth |
|---|---|---|
| GET | `/agent/config/{report_uuid}/VerinFastConfig.yaml` | none — uuid is the secret; `?scan=code\|cloud` filters |
| POST/GET | `/agent/config/{report_id}` | bearer JWT + company ABAC (the UI, not the agent) |

The served YAML sets `report.uuid`, `modules.code.git.start`,
`modules.code.dependencies`, `modules.cloud[]`, `repos[]`, `local_repos[]`,
`should_upload`, `dry`, `truncate_findings` (**default true**),
`truncate_findings_length` (**default 30**), and pins
`server.code_separator: /CodeScan`. No other `server:` keys are emitted.

## 6. Response semantics

- **200** — accepted.
- **404** — unknown report, unknown scan session. Also returned instead of 403
  so the routes are never an existence oracle.
- **415** — ClamAV rejected the payload. **Not retryable.**
- **502** — antivirus unavailable. Retryable.
- **422** — pydantic shape rejection. Indicates an agent bug, not a transient
  failure; ATD deliberately avoids 422 for lookup misses.

## 7. Things ATD works around today

Recorded so v2 can retire them, without breaking agents still in the field:

- ~~The agent's default `code_separator` is the old product name.~~ **Fixed on
  `main` in PR #814** (`4ae508b`), after this page's base revision. ATD still
  pins `/CodeScan` in every served config because agents already in the field
  predate the fix — so the pin stays load-bearing even though the default is
  now correct.
- `modules.code.git.start` is ignored by the agent (a typo in `config.py`), so
  ATD emits its preferred window "for forward compatibility" and depends on
  none of it.
- Stats paths contain `temp_repo/`, so ATD rewrites them to `./`.

## Related

[[Requirements: ATD v3 Integration]] · [[Feature: Upload & Report Addressing]]
