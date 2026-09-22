---
title: v1 Architecture (As-Is)
parent: verinfast-v2
revision: ea5ad24
tags: v2, architecture
---

# v1 Architecture (As-Is)

4,455 lines of Python across 34 modules, plus 17 test modules.

```
src/verinfast/
  agent.py          929   orchestration + git + sizes + cloud dispatch + upload + main()
  config.py         507   argparse + YAML + dataclasses + defaults
  code_scan.py      145   semgrep + cache
  upload.py          67   URL construction  ← the ATD contract lives here
  user.py            94   interactive consent prompts
  system/sysinfo.py  30
  utils/
    utils.py        203   logging, exec, truncation, repo-URL parsing
    license.py       52   telemetry POST
    git_metrics.py   73   per-commit modernmetric — not called by anything
  cloud/
    aws/            520   costs, instances, blocks, regions, profile (via aws CLI)
    azure/          300   costs, instances, blocks (via azure-mgmt SDKs)
    gcp/            418   instances, blocks, zones (via google-cloud SDKs)
  dependencies/
    walk.py         136   fixed-order orchestration of nine walkers
    walkers/        ~920  one per ecosystem + shared Walker/Entry base
  templates/results.j2    the local HTML report
```

## Control flow

```
main()
 └─ Agent()                      ← reads argv, prompts for consent, opens cache
     ├─ preflight()              ← git ls-remote each repo, check CLIs, prompt y/N, exit(0) on no
     └─ scan()
         ├─ report_license()     ← telemetry POST
         ├─ get_system_info()
         ├─ scanRepos()
         │   ├─ for each remote repo: clone → ~/.verinfast/temp_repo → parseRepo()
         │   └─ for each local repo: parseRepo() in place
         │        └─ parseRepo(): git init → checkout → git log → sizes walk →
         │           modernmetric → run_scan(semgrep) → dependency_walk()
         │           (each stage writes a file, uploads it, and mutates
         │            the module-global `template_definition`)
         ├─ scanCloud()          ← if/elif chain over aws|azure|gcp
         └─ create_template()    ← renders template_definition
```

## The five structural problems

1. **`Agent` is the whole program.** Orchestration, git parsing, filesystem
   walking, cloud dispatch and HTTP upload all live on one class, in one file.
2. **Global mutable state.** `template_definition` at module scope, mutated by
   every stage and by `code_scan.run_scan`, which takes it as a parameter.
3. **`os.chdir()` as control flow.** `parseRepo` chdirs into the repo and
   relies on the caller restoring `curr_dir`; three walkers chdir into each
   install point. Any concurrency or re-entrancy corrupts this.
4. **Fixed global paths.** One clone directory (`~/.verinfast/temp_repo`), one
   cache (`~/.verinfast_cache`), one preferences file (`~/.verinfast/`).
5. **CLI assumptions baked into the core.** argv parsing in `Config.__init__`,
   `input()` in `Agent.__init__`, `print()` for progress, `exit(0)` in
   preflight.

Each of these maps directly to a blocker in
[[Requirements: Embeddable Library API]].

## What v1 gets right, and v2 should preserve

- **`upload.py` is a clean, pure path builder** — small enough that ATD v3
  vendors a literal port of it as a contract test. Keep that shape.
- **The walker pattern.** `Walker` + `Entry` with one subclass per ecosystem is
  the right decomposition; the base class just needs a coherent interface.
- **Dry-run mode** genuinely exercises the upload path without scanning, which
  is why ATD could build against it.
- **Offline inspection** (`should_upload: false` + `--output`) is a real
  privacy feature, not a debug flag.
- **The test fixtures** for the dependency walkers are good and should port
  across unchanged.

## Proposed v2 shape

Sketch only — workstream 3 owns this.

```
verinfast/
  __init__.py            public API: Scanner, ScanConfig, ScanResult
  config/                schema, loaders (dict|file|url), defaults
  core/                  Scanner, per-scan context (paths, logger, progress)
  scanners/              git, sizes, stats, findings, dependencies   (one protocol)
  cloud/                 providers/{aws,azure,gcp} behind one protocol
  transport/             upload paths, HTTP client, retry
  reporting/             local HTML + run summary
  cli/                   argparse, prompts, progress — the only place that may print
```

with README.md + CLAUDE.md in each.
