---
title: VerinFast v2
status: drafting
phase: 1 — Document features, goals, requirements
owner: Jason
updated: 2026-09-23
tags: v2, index
---

# VerinFast v2

VerinFast is the **scanning agent** of the VerinFast product family: it runs on
someone else's machine, inside someone else's network, looks at their source
code and cloud accounts, and ships back *summary data only* — never the code,
never the credentials.

v1 works. It is also nine hundred lines of `Agent.scan()`, a module-level
mutable dict, `os.chdir()` as control flow, and a prompt for consent inside a
constructor. It cannot be imported. This wiki is the design record for the
clean rewrite.

## The five things v2 must do

| # | Workstream | State |
|---|---|---|
| 1 | Document features, goals, requirements | **this wiki** |
| 2 | Dependency keep/replace + license confirmation | done — [[Dependency & License Review]] + [[Semgrep Alternatives]] |
| 3 | Re-architect the folder structure to current standards | skeleton landed — see [[Decisions Landed]] |
| 4 | Rebuild against `atd_v3` in good-place (matching API signatures) | transport pinned; scanners not started — [[ATD v3 Upload Contract]] |
| 5 | Importable as a Python module so ATD v3 can scan on demand | config surface landed; API not built — [[Requirements: Embeddable Library API]] |

## Start here

- [[Goals & Non-Goals]] — what v2 is for, and what it deliberately is not
- [[Feature Inventory]] — everything v1 does today, one page per capability
- [[Requirements]] — what v2 must satisfy
- [[v1 Architecture (As-Is)]] — the map of the thing being replaced
- [[Known Defects & Debt]] — what the review turned up; each one is a v2 requirement in disguise
- [[Open Questions]] — decisions still needed
- [[Decisions Landed]] — what has been settled, and why
- [[v2 Workstreams]] — sequencing

## Source of truth

Everything here was derived by reading `VerinFast/verinfast@ea5ad24` and
`VerinFast/good-place@74e41ff` (`services/atd`). Where the two disagree,
good-place is the customer and wins — see [[ATD v3 Upload Contract]].

`main` has since advanced to `438d291`, which carries the v2 skeleton and the
vendored ruleset. [[Decisions Landed]] tracks what changed; the as-is pages
still describe `ea5ad24`, which is the thing being replaced.
