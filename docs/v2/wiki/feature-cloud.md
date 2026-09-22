---
title: Feature: Cloud Cost & Inventory
parent: features
artifacts: costs, instances, instance_utilization, storage
tags: v2, feature, cloud
---

# Feature: Cloud Cost & Inventory

## What it produces

Four artifacts per provider account, each in the shared envelope ATD v3
expects:

```
{"metadata": {"provider": "aws|azure|gcp", "account": "<id>"}, "data": [...]}
```

| Artifact | Route | Content |
|---|---|---|
| Costs | `costs` | daily blended cost grouped by service |
| Instances | `instances` | compute inventory (type, region, state, tags) |
| Utilization | `instance_utilization` | CPU/mem/disk min-avg-max time series |
| Block storage | `storage` | volumes/buckets, size, type, permissions |

`cloud/cloud_dataclass.py` holds the shared `Utilization_Datapoint` /
`Utilization_Datum` types that normalise the three providers' metric shapes
into `{timestamp, cpu{min,avg,max}, mem{...}, hdd{...}}`.

## How v1 does it

Three very different mechanisms, which is the main thing to fix:

- **AWS** — shells out to the `aws` CLI (`aws ce get-cost-and-usage`,
  paginated by `--next-page-token`) with `shell=True` and a config-supplied
  profile name interpolated into the string. Credentials come from a CLI
  profile discovered by `cloud/aws/get_profile.py`.
- **Azure** — the `azure-mgmt-*` / `azure-identity` / `azure-monitor-query`
  SDKs, in-process. Requires `az login` to have happened.
- **GCP** — the `google-cloud-compute` / `-storage` / `-monitoring` SDKs,
  in-process. Requires `gcloud` auth.

Utilization is written as a side-file (`{provider}-instances-{account}-utilization.json`)
by the instances collector and uploaded only if it exists.

## Defects

- **Azure and GCP utilization are uploaded with `source="AWS"`.**
  `agent.py` lines ~824 and ~865 both pass `source="AWS"` — a copy-paste bug.
  `source` only affects the log line (the route has no repo segment), so no data
  is misfiled, but every log says AWS.
- The whole per-provider block is wrapped in one bare `except:` that logs and
  continues, so a credential error and a parse error are indistinguishable.
- Provider dispatch is a 150-line `if provider.provider == "aws": ... if ==
  "azure": ... if == "gcp": ...` chain inside `scanCloud()` — the clearest case
  in the codebase for a plugin interface.

## New collectors v2 owes ATD v3

ATD v3 has shipped ingest, models and migrations for two artifacts **no agent
produces yet**:

| Artifact | Route | Source data |
|---|---|---|
| Cloud user activity | `POST /report/uuid/{uuid}/user_activity` | AWS CloudTrail; Azure sign-in + audit logs; GCP admin activity logs |
| Load balancers | `POST /report/uuid/{uuid}/load_balancers` | AWS ELB/ALB/NLB; Azure LB + App Gateway; GCP forwarding rules |

Same uuid-gated contract, same envelope, upsert-keyed on
`(report_id, provider, account, remote_id)`. The corresponding widgets are
blocked until v2 ships these. Treated as **in scope** — see
[[Requirements: Functional]].

## What v2 must change

- One `CloudProvider` interface — `costs()`, `instances()`, `utilization()`,
  `storage()`, `user_activity()`, `load_balancers()` — with three
  implementations, so adding a provider or an artifact is additive.
- Drop the AWS CLI shell-out in favour of `boto3` (already a dependency), which
  removes the `shell=True` string interpolation and the "is the CLI installed"
  preflight for AWS.
- Per-artifact error reporting instead of one swallowing `except:`.

## Related

[[ATD v3 Upload Contract]] · [[Known Defects & Debt]]
