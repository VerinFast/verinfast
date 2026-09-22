---
title: Feature: Scan Caching
parent: features
module: cachehash
tags: v2, feature, plumbing
---

# Feature: Scan Caching

## What it does

Semgrep is the slowest part of a scan, so results are cached in a SQLite
database at `~/.verinfast_cache/semgrep.db` (table `semgrep_cache`) via the
third-party `cachehash` package. `code_scan.run_scan` calls `cache.get(path)`;
a hit writes the cached JSON straight to the findings file and skips Semgrep
entirely.

## Open risk — verify before relying on it

The cache key is the **scan path**. For every remote repository the scan path
is the *same* directory — `~/.verinfast/temp_repo` — because the agent clones
each repo into that one location in turn. Whether that is safe depends
entirely on whether `cachehash` hashes the directory *contents* behind the
scenes (its name suggests it does) or just the path string.

If it keys on the path alone, scanning repo A then repo B in one run would
serve A's findings for B. **This must be proven with a test before v2 keeps the
design** — see [[Open Questions]].

## Defects

- `cachehash` is imported directly by `agent.py` and `code_scan.py` but is
  **not declared in `pyproject.toml`**. It resolves today only because
  `modernmetric>=1.5.9` depends on `cachehash>=1.1.4`. A modernmetric release
  that drops it breaks `pip install verinfast` with an ImportError at startup.
- There is no cache invalidation, no TTL, no size bound, and no way to clear it
  from the CLI. The rule registry `--config auto` pulls can change underneath a
  cached result, so a cache hit can hide a newly-published rule.
- The cache lives in `~`, which in library mode means "whatever user the ATD v3
  worker runs as" — a shared, unbounded, cross-tenant cache. Library mode needs
  either an explicit cache directory or no cache at all.

## What v2 must change

- Key on a **content digest of the scanned tree plus the Semgrep ruleset
  version**, not a path.
- Declare the dependency explicitly, or drop it for a small in-repo cache.
- Make the cache location an explicit parameter; default to disabled in library
  mode.

## Related

[[Feature: Security Scan (Semgrep)]] · [[Requirements: Embeddable Library API]]
