---
title: Feature Inventory
parent: verinfast-v2
tags: v2, features, index
---

# Feature Inventory

Everything v1 does today. One page per capability; each records **what it
produces**, **how it does it now**, and **what v2 must keep or change**.

This is the regression checklist for the rewrite: if a page here has no
counterpart in v2, the product lost something.

## Code

- [[Feature: Security Scan (Semgrep)]] — OWASP/CWE findings per repo
- [[Feature: Git History]] — commits, authorship, per-file churn
- [[Feature: File Inventory & Sizes]] — every file's size, LOC, extension
- [[Feature: Code Statistics (Modernmetric)]] — complexity, Halstead, maintainability, language mix
- [[Feature: Dependency & License Inventory]] — nine package ecosystems

## Cloud

- [[Feature: Cloud Cost & Inventory]] — AWS, Azure, GCP costs, instances, storage, utilization

## Host

- [[Feature: Host System Info]] — the machine the scan ran on

## Plumbing

- [[Feature: Configuration & CLI]] — YAML (local or remote) plus argv
- [[Feature: Upload & Report Addressing]] — how results reach the server
- [[Feature: Scan Caching]] — skip re-scanning unchanged trees
- [[Feature: Privacy Controls]] — truncation, consent, what never leaves
- [[Feature: Local HTML Report]] — the offline results page

## Coverage note

Two capabilities exist on the **server** side and are waiting on this agent:

| Waiting on VerinFast | ATD v3 ingest route | Blocking |
|---|---|---|
| Cloud user activity (CloudTrail / Azure sign-in / GCP admin logs) | `POST /report/uuid/{uuid}/user_activity` | `CloudUserActivityWidget` |
| Load balancer inventory (ELB/ALB/NLB, Azure LB/AppGW, GCP forwarding rules) | `POST /report/uuid/{uuid}/load_balancers` | `LoadBalancerWidget` |

Both tables stay empty until v2 grows the collectors. They are **new
features**, not ports — see [[Requirements: Functional]].
