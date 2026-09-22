---
title: Feature: Local HTML Report
parent: features
template: src/verinfast/templates/results.j2
tags: v2, feature, reporting
---

# Feature: Local HTML Report

## What it does

At the end of a non-dry scan, `Agent.create_template()` renders
`templates/results.j2` with Jinja2 (autoescape on for html/xml) into
`<output_dir>/results.html` — a Bootstrap-styled page with sections for file
sizes, git log (first 100 commits), stats, findings and dependencies.

It is the only thing a customer sees if they never upload.

## How the data gets there

Through a **module-level mutable dict**, `template_definition`, in `agent.py`.
Each scan stage reaches out and writes its slice into it
(`template_definition["gitlog"] = ...`, `["sizes"]`, `["stats"]`,
`["gitfindings"]`, `["dependencies"]`, `["filelist"]`). `code_scan.run_scan`
takes it as a parameter and mutates it.

This single global is the reason two scans cannot run in one process, and the
reason a second scan in the same process would render the first scan's data.

## Defects

- Global mutable state (above).
- The whole call is wrapped in a bare `except:` that logs
  `"Template Creation Failed"` and discards the exception, so a template bug is
  invisible.
- With multiple repos configured, each `parseRepo` overwrites the previous
  repo's entries — the report shows the **last** repo only, silently.
- Bootstrap is loaded from a CDN, so the "offline report" needs the internet.

## What v2 must change

- Reporting consumes a **returned result object**, not a global.
- One report per scan, with a section per repository.
- Vendor the CSS so the local report works air-gapped.
- Let the exception surface, or at least log it.

## Related

[[Requirements: Embeddable Library API]] · [[v1 Architecture (As-Is)]]
