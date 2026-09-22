---
title: Requirements: Non-Functional
parent: requirements
tags: v2, requirements
---

# Requirements: Non-Functional

## Portability

- **N1 (MUST)** Python 3.11+ on Linux and macOS. Windows: everything except
  Semgrep, degrading with a clear message rather than failing.
- **N2 (MUST)** No dependency that exists only to satisfy an accidental import.
  `windows-curses` is currently required because `npm.py` imports `isdigit`
  from `curses.ascii`.
- **N3 (MUST)** Every runtime import declared in `pyproject.toml`.
  `cachehash` is currently undeclared and resolves only transitively through
  `modernmetric`.
- **N4 (SHOULD)** A container image that actually runs the agent. The current
  `Dockerfile` installs `verinfast` from PyPI (not the source being built) and
  declares no `ENTRYPOINT`, so `docker run` does nothing.

## Structure

- **N5 (MUST)** README.md and CLAUDE.md in every folder, matching good-place's
  convention.
- **N6 (MUST)** A per-file line ceiling (good-place uses 500; confirm in
  [[Open Questions]]). `agent.py` is 929 lines and `config.py` is 507.
- **N7 (MUST)** One domain per module; no module both orchestrates and parses.
- **N8 (MUST)** No module-level mutable state and no import-time side effects —
  `patch_pygments()`, argv parsing and timestamped defaults all run at import
  today.

## Observability

- **N9 (MUST)** Structured logging through the standard `logging` module, with
  an injectable handler. The current `DebugLog` opens, appends and closes the
  log file on **every line**, formats its own timestamps, and uses
  `inspect.stack()` to guess a tag when none is given.
- **N10 (MUST)** No bare `except:`. There are more than a dozen; several hide
  real failures (template rendering, cloud provider errors, `.err` upload).
- **N11 (SHOULD)** Progress reporting as a callback, not `print()` — the
  dependency walker currently prints fixed "Dependency Scan 40%" milestones.

## Performance

- **N12 (SHOULD)** One filesystem traversal per repository, not three.
- **N13 (SHOULD)** One `git log` invocation per repository, not six per commit.
- **N14 (SHOULD)** Write each artifact once. `dependencies/walk.py` rewrites
  the dependency file after every walker — eight redundant serialisations.
- **N15 (SHOULD)** Skip line-counting binary files.

## Testing

- **N16 (MUST)** The suite runs offline: no network, no cloud credentials, no
  package managers. Fixtures already exist for most walkers.
- **N17 (MUST)** A contract test that builds every upload path and asserts it
  against the same golden cases ATD v3's `tests/e2e/upload_paths.py` uses, so
  drift on either side fails loudly.
- **N18 (MUST)** One config source of truth for pytest. `pytest.ini` and
  `[tool.pytest.ini_options]` in `pyproject.toml` both exist today and
  disagree; `pytest.ini` silently wins.
- **N19 (SHOULD)** Coverage on the library API surface specifically, since that
  is what ATD v3 depends on.

## Versioning & release

- **N20 (MUST)** A real version. `VERSION.py` is pinned at
  `2023.08.15115926` while `make_version.py` sits unused beside it, and
  `license.py` reports that string as the agent version on every run.
- **N21 (SHOULD)** Publish to PyPI as today — ATD v3's live e2e test installs
  the real package from there.
