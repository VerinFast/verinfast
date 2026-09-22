---
title: Dependency & License Review
parent: verinfast-v2
status: stub — workstream 2
tags: v2, licensing, dependencies
---

# Dependency & License Review

**Status: stub.** This page is the deliverable of workstream 2 and is not yet
filled in. What follows is the inventory to review, so the work can start from
a list rather than a `pyproject.toml`.

## The current runtime surface

From `pyproject.toml` at `ea5ad24`:

### Cloud SDKs
`azure-identity`, `azure-mgmt-compute`, `azure-mgmt-monitor`,
`azure-mgmt-network`, `azure-mgmt-resource`, `azure-mgmt-storage`,
`azure-monitor-query`, `boto3`, `google-cloud-compute`, `google-cloud-storage`,
`google-cloud-monitoring`

*Question for review:* nine cloud packages plus the `aws` CLI shell-out. AWS
costs and instances go through the CLI even though `boto3` is already a
dependency.

### Scanners
`semgrep` (pinned `==1.152.0`), `modernmetric`, `johnnydep`, `gemfileparser`,
`pygments-tsx`

*Question for review:* `semgrep`'s license is the one to confirm first — the
product ships commercially, and Semgrep's licensing has changed over time.
`modernmetric` is the transitive source of the undeclared `cachehash`.

### Plumbing
`httpx[http2]`, `Jinja2` (pinned `==3.1.6`), `pyyaml`, `psutil`, `defusedxml`,
`tomli` (py<3.11), `windows-curses` (win32)

*Question for review:* `windows-curses` exists only because `walkers/npm.py`
imports `isdigit` from `curses.ascii` (D12). Removing that import removes the
dependency.

### Undeclared but imported
`cachehash` — see D11.

### Dev
`black`, `pytest`, `pytest-cov`, `pytest-xdist`, `coverage`

## What this page must contain when complete

For each dependency:

| Column | Meaning |
|---|---|
| Package | name + version floor/pin |
| License | SPDX identifier, **verified from the distribution**, not from memory |
| Compatible? | against VerinFast's own CC BY-NC 4.0 licensing and commercial use |
| Keep / Replace / Drop | with a one-line reason |
| Replacement | if replacing |
| Transitive risk | anything it drags in that matters |

Plus a rollup: total transitive package count, any copyleft in the tree, and
any package whose license changed since it was adopted.

## Note on VerinFast's own license

The repo ships **Creative Commons Attribution-NonCommercial 4.0** (see
`LICENSE`), and `pyproject.toml` classifies as "Free for non-commercial use".
Worth confirming during this workstream that the chosen license is still
intended — CC licenses are not designed for software, and the non-commercial
clause interacts awkwardly with being imported into a hosted commercial
service (which is exactly what workstream 5 is).

## Related

[[Feature: Dependency & License Inventory]] · [[Requirements: Security & Privacy]] · [[v2 Workstreams]]
