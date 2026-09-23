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

`base.py` defines the protocol. All three providers are stubs.
