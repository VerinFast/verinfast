---
title: Known Defects & Debt
parent: verinfast-v2
revision: ea5ad24
tags: v2, defects
---

# Known Defects & Debt

Found by reading `main` at `ea5ad24`. Each is a v2 requirement in disguise;
the right-hand column says which.

## Correctness

| # | Defect | Where | Requirement |
|---|---|---|---|
| D1 | `modules.code.git.start` never applies — `g = ["git"]` should be `g = c["git"]`, then `"start" in g` tests a literal list | `config.py` ~496 | F12 |
| D2 | `run_sizes` is read from config and reported to telemetry but gates nothing | `config.py` 492, `agent.py` | F13 |
| D3 | `git init` is run against the scan target, creating `.git` in a user directory that was not a repo | `agent.py::parseRepo` | F2, S12 |
| D4 | Azure and GCP utilization uploads both pass `source="AWS"` | `agent.py` ~824, ~865 | — (log-only) |
| D5 | The local HTML report shows only the **last** repository — every `parseRepo` overwrites the shared `template_definition` | `agent.py` | F17 |
| D6 | The downloaded remote config (containing the report UUID) is never deleted despite `delete_config_after = True` | `config.py` | S5 |
| D7 | Default dates are non-ISO (`2026-3-1`) | `config.py` | F11 |
| D8 | `signed` is `True` for every `git show --format='%G?'` value except a bare `N`, and the value arrives quote-wrapped | `agent.py::formatGitHash` | see [[Open Questions]] |
| D9 | `std_exec` falls back to `subprocess.check_output(cmd, shell=True)` **with a list**, which on POSIX runs only `cmd[0]` | `utils/utils.py` | S9 |
| D10 | `allowfile()` ignores the `STD_EXCLUDE_LIST` defined two files away, so `venv/`, `dist/`, `__pycache__` are all walked and counted | `agent.py`, `utils/utils.py` | F6 |

## Packaging

| # | Defect | Where | Requirement |
|---|---|---|---|
| D11 | `cachehash` is imported directly but not declared; it resolves only transitively via `modernmetric>=1.5.9` | `pyproject.toml` | N3 |
| D12 | `windows-curses` is a dependency solely because `npm.py` does `from curses.ascii import isdigit` | `walkers/npm.py` | N2 |
| D13 | `VERSION.py` is frozen at `2023.08.15115926`; `make_version.py` is unused; that string is reported as the agent version in telemetry | repo root | N20 |
| D14 | `Dockerfile` installs `verinfast` from PyPI rather than the source being built, and has no `ENTRYPOINT` — `docker run` does nothing | `Dockerfile` | N4 |
| D15 | `pytest.ini` and `[tool.pytest.ini_options]` both exist and disagree; `pytest.ini` wins silently | repo root | N18 |
| D16 | README claims Python 3.9+; `pyproject.toml` requires `>=3.11,<=3.14`; a `semgrep` marker still branches on 3.9 | `README.md`, `pyproject.toml` | N1 |

## Robustness

| # | Defect | Where | Requirement |
|---|---|---|---|
| D17 | A dozen bare `except:` clauses, several hiding real failures (template render, cloud provider, `.err` upload, `getloc`) | throughout | N10 |
| D18 | `semgrep.commands.scan` and `modernmetric.__main__.main` are called as in-process CLIs; completion arrives as `SystemExit` | `code_scan.py`, `agent.py` | L6 |
| D19 | `DebugLog` opens/appends/closes the log file on every single line, and uses `inspect.stack()` to synthesise a tag | `utils/utils.py` | N9 |
| D20 | Failing to write `system_info.json` raises `RuntimeError` and aborts the entire scan | `agent.py` | F19 |
| D21 | `getUrl()` returns `None` on any error, so a registry outage silently yields a license-free dependency inventory | `walkers/classes.py` | F6 |
| D22 | No upload retry at all; the first 5xx loses that artifact for the run | `agent.py::upload` | F20 |

## Performance

| # | Defect | Where | Requirement |
|---|---|---|---|
| D23 | Six `git` subprocesses per commit | `agent.py::formatGitHash` | N13 |
| D24 | Three full filesystem walks per repo | `agent.py::parseRepo` | N12 |
| D25 | The dependency file is rewritten after each of the eight walkers | `dependencies/walk.py` | N14 |
| D26 | Binary files are read line-by-line for LOC | `agent.py::getloc` | N15 |

## Design

| # | Debt | Where | Requirement |
|---|---|---|---|
| D27 | `Walker.initialize(self, command)` vs. subclasses' `initialize(self, root_path)` — the base is never usable polymorphically | `walkers/` | N7 |
| D28 | `Entry` subclasses `dict` but stores state in attributes, so it is an empty dict | `walkers/classes.py` | N7 |
| D29 | `utils/git_metrics.py` is never called from anywhere | `utils/` | [[Open Questions]] |
| D30 | `config.config` is initialised to the `FileNotFoundError` **class** as a sentinel | `config.py` | N7 |
| D31 | `"pytest" in sys.argv[0]` is the only thing distinguishing library use from CLI use | `config.py` | L1 |
| D32 | `printable.__str__` walks `dir(self)`, calling every non-callable attribute | `config.py` | N7 |

## Security

Covered in full on [[Requirements: Security & Privacy]]. The headline items:
unconditional `npm`/`composer`/`gem install` against scanned code (S7),
undocumented telemetry (S4), `shell=True` with interpolated values (S9), and
the report UUID left on disk (S5).
