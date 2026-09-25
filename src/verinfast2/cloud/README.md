# cloud/

AWS, Azure and GCP behind one provider protocol.

| File | What |
| ---- | ---- |
| `base.py` | the `CloudProvider` protocol and `provider_for()` |
| `aws.py` | Amazon Web Services |
| `azure.py` | Azure |
| `gcp.py` | Google Cloud |

## Six artifacts per account

`costs`, `instances`, `utilization`, `storage`, and — new in v2 —
`user_activity` and `load_balancers`.

Those last two matter: ATD v3 has already shipped the ingest routes, models,
migration and widgets for both, and they stay empty until this agent produces
them. They are the one piece of net-new collection work in v2.

## Why a protocol

v1 dispatched through a 150-line `if provider == "aws": ... if == "azure": ...`
chain inside `Agent.scanCloud`, wrapped in one bare `except:` that made a
credential error and a parse error look identical. Adding a provider or an
artifact meant editing that chain. Here it is additive.

## AWS moves to boto3

v1 shells out to the `aws` CLI with `shell=True` and a config-supplied profile
name interpolated into the command string. `boto3` is already a dependency,
so the shell-out buys nothing and costs an injection surface.

## Current state

| | `costs` | `instances` | `utilization` | `storage` | `user_activity` | `load_balancers` |
| --- | --- | --- | --- | --- | --- | --- |
| **aws** | skipped | skipped | skipped | skipped | **collected** | **collected** |
| **azure** | skipped | skipped | skipped | skipped | skipped | skipped |
| **gcp** | skipped | skipped | skipped | skipped | skipped | skipped |

"Skipped" is a real `ArtifactResult` with `Outcome.SKIPPED` and a reason, not
an exception and not an empty success. A scan of an Azure account today
returns six results saying nobody has written these yet — which is a
different answer from six saying the account has nothing, and `F18` is the
requirement that they never look alike.

The four ported artifacts say `not ported from v1 yet`; GCP costs says
something else, because v1 collected no GCP costs at all and "not ported"
would misdescribe why it is empty.

## The region sweep

Both AWS collectors are regional, so both sweep every region the installed
botocore reports for the service — read from its bundled endpoint data, no
call and no network, rather than the hardcoded list v1 carried, which silently
stops covering any region added after it was written.

A region that refuses is normal, not exceptional: opt-in regions return
`AuthFailure` for accounts that have not enabled them. So a per-region error
is recorded and the sweep continues, and the artifact is `FAILED` only if
*every* region failed. One disabled region must not turn a good inventory into
no inventory; equally, an inventory where every call raised is not an account
with no load balancers.

## Result helpers

`base.py` exports `ok()`, `skipped()` and `failed()`. Providers build results
through them so the three cannot drift into three spellings of "this didn't
run", and so the `F18` distinction stays visible at this layer.

## Known gaps

- `target_count` is left unset for ALB/NLB. A real count means describing
  every target group and then every group's health — two more calls per
  balancer per region — and ATD's column is nullable with the widget reading
  absent as unknown. Classic ELBs report it for free, from `Instances`.
- Classic ELBs have no ARN, so their `id` is `classic/<region>/<name>`. Names
  are only unique within a region, and the ATD upsert key is
  `(report, provider, account, remote_id)` — unqualified, two same-named
  balancers in two regions would collapse onto one row.
