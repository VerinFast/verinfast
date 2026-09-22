---
title: Goals & Non-Goals
parent: verinfast-v2
tags: v2, goals
---

# Goals & Non-Goals

## What VerinFast is

A **portable, low-trust scanning agent**. Someone doing technical diligence on
a company cannot get a copy of that company's source code — so instead the
company runs VerinFast themselves, inside their own perimeter, and only
aggregate measurements leave the building.

That framing sets every constraint that follows: the agent runs on hardware we
do not control, with credentials we never see, against code we are not allowed
to keep.

## Goals for v2

1. **Preserve the measurement surface.** Every artifact v1 produces
   ([[Feature Inventory]]) still gets produced. A v2 that measures less is a
   regression in the product, not a simplification.
2. **Be a library first, a CLI second.** The scanning engine is an importable
   package with a typed API; the CLI is a thin shell over it. ATD v3 must be
   able to `import verinfast` and scan a code sample in-process
   ([[Requirements: Embeddable Library API]]).
3. **Match `atd_v3`'s API exactly.** The upload contract is owned by
   good-place's `services/atd`, and it is already pinned by a contract test on
   that side. v2 conforms to it rather than negotiating with it
   ([[ATD v3 Upload Contract]]).
4. **No hidden global state.** No module-level mutable dicts, no `os.chdir()`,
   no `sys.argv` parsing at import time, no `input()` inside a constructor.
   These are the four things that make v1 un-importable.
5. **Explicit, auditable trust boundaries.** Today the agent silently runs
   `npm install`, `composer install` and `gem install` against the code it is
   scanning, and phones a telemetry endpoint on every run. Both may be fine —
   but in v2 they are *declared*, *configurable*, and *off by default in
   library mode* ([[Requirements: Security & Privacy]]).
6. **Standards-conformant layout.** README.md + CLAUDE.md in every folder,
   file-size limits, one domain per module — matching how good-place is
   organised, so a developer moves between the two without re-learning.
7. **Testable without the network, the cloud, or a package manager.** v1's
   suite already leans this way; v2 makes it structural.

## Non-Goals

- **Not a CI gate.** VerinFast is a point-in-time diligence snapshot, not a
  pass/fail build step. No exit-code contract, no "fail on severity >= high".
- **Not a replacement for Semgrep/modernmetric/johnnydep.** v2 orchestrates
  best-in-class scanners; it does not write its own SAST engine or its own
  complexity metrics.
- **Not a server.** No long-running daemon, no scheduler, no queue. ATD v3
  owns orchestration; VerinFast owns one scan.
- **Not a code exfiltration tool.** The agent must never upload source. The
  closest it gets — Semgrep finding snippets — is already length-capped by the
  truncation feature, and that cap stays.
- **Not multi-tenant.** One scan, one report id, one process.

## Success criteria

v2 is done when:

- `atd_api`'s `tests/e2e/test_agent_contract.py` passes against a v2 agent with
  no changes on the ATD side.
- ATD v3 can scan a code sample in-process with no subprocess of VerinFast
  itself, no `chdir`, and no prompt.
- Every folder has README.md + CLAUDE.md, and no module exceeds the line
  ceiling agreed in [[Open Questions]].
- Every third-party dependency has a confirmed, compatible license recorded in
  [[Dependency & License Review]].
