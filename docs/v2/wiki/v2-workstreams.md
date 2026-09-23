---
title: v2 Workstreams
parent: verinfast-v2
tags: v2, plan
---

# v2 Workstreams

## 1 — Document features, goals, requirements ← *this wiki*

**Deliverable:** this wiki.

Done when [[Feature Inventory]], [[Requirements]], [[ATD v3 Upload Contract]]
and [[Known Defects & Debt]] are reviewed and [[Open Questions]] has answers.

## 2 — Dependency keep/replace + license confirmation ← *done*

**Deliverable:** [[Dependency & License Review]], filled in, plus
[[Semgrep Alternatives]] — which was scoped in mid-stream when the registry
licensing turned out to be the sharp edge rather than the engine licence.

Sequenced second because the answers change the architecture: whether AWS goes
through `boto3` or the CLI, whether Semgrep can be pinned or must be
subprocessed, and whether the eleven cloud SDKs stay in the base install or move
behind extras.

Outcome: Opengrep in, vendored MIT rulesets in, `--config auto` out. See
[[Decisions Landed]] D-1 and D-2. Q11 and Q12 came out of this workstream and
are counsel's, not engineering's.

## 3 — Re-architect the folder structure ← *partly landed*

**Deliverable:** the new tree, README.md + CLAUDE.md in every folder, line
ceiling enforced.

The skeleton is on `main` at `438d291`: `models`, `config`, `transport`,
`core`, `scanners`, `rules`, with README.md + CLAUDE.md parity and the line
ceiling held. What is *not* done is the scanners themselves — only the ruleset
loader exists.

Still blocked on: Q1 (isolation model) and Q2 (result model). The cloud-SDK
verdict from workstream 2 is in but unapplied.

Sketch in [[v1 Architecture (As-Is)]] § *Proposed v2 shape*; the landed
decisions in [[Decisions Landed]].

## 4 — Rebuild against atd_v3

**Deliverable:** an agent that passes ATD v3's
`tests/e2e/test_agent_contract.py` unchanged, plus the two new cloud
collectors (F8).

The contract is already captured in [[ATD v3 Upload Contract]] and pinned by
44 tests in `tests/v2/test_upload_paths.py` ([[Decisions Landed]] D-3), so this
workstream is implementation, not discovery. The one thing to confirm with the
ATD side: whether they want the `user_activity` and `load_balancers` collectors
in the first v2 release or a follow-up.

## 5 — Importable as a Python module

**Deliverable:** the public API in
[[Requirements: Embeddable Library API]], consumed by ATD v3 against a code
sample with no git history, no remote, no report UUID and no upload.

Blocked on: 3 (the structure *is* the API) and Q1/Q3.

## Sequencing

```
1 ──┬── 2 ✓ ──┬── 3 (skeleton ✓, scanners ✗) ── 4
    │         │                                  └── 5
    └── Q1…Q10 ──────────────────────────────────┘
```

Workstreams 2 and the open questions run in parallel with the tail of 1.
Workstream 4 and 5 both depend on 3, but 4's contract is already known, so its
transport layer can be built against the contract page before 3 lands.

## Not in any workstream

- Migrating existing customers. v2 is a new major; the field will run v1 for a
  while, which is why [[ATD v3 Upload Contract]] § 7 records the workarounds
  ATD must keep.
- The OSS-embeddings pipeline (ATD's `/oss` route). Separate producer today.
