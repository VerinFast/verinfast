---
title: Dependency & License Review
parent: verinfast-v2
workstream: 2
status: complete — decisions pending
method: licenses read from installed distributions, not from memory
verified: 2026-09-23
tags: v2, licensing, dependencies
---

# Dependency & License Review

Workstream 2: **which dependencies v2 keeps, replaces or drops, and what each one
is licensed under.**

## Method

Every license below was read out of the **installed distribution** —
`License-Expression`, then the `License` field, then the trove classifiers, and
for anything still ambiguous the actual `LICENSE` file shipped in the wheel.
Nothing here is recalled.

```sh
python -m venv env && env/bin/pip install ".[dev]"
# then read importlib.metadata for every resulting distribution
```

Resolved on Python 3.11 / Linux against `pyproject.toml` at `ea5ad24`.
**141 distributions** install: **127 runtime** (including the `httpx[http2]`
and gRPC extras), **12 dev-only**, plus `setuptools` and VerinFast itself.

## Rollup

All 140 third-party distributions (everything except VerinFast itself):

| License | Count |
|---|---|
| MIT | 66 |
| Apache-2.0 | 30 |
| BSD-3-Clause | 23 |
| BSD-2-Clause | 6 |
| MPL-2.0 | 2 |
| **LGPL-2.1-or-later** | **2** |
| **CC-BY-NC-4.0** | **2** |
| **CC-BY-NC-ND-4.0** | **1** |
| GPL-3.0-or-later OR MIT (dual) | 1 |
| PSFL / PSF-2.0 | 2 |
| MIT-0 | 1 |
| Multi-licensed permissive (`A OR B`, `A AND B`) | 4 |

**No unlicensed package, and no strong copyleft that cannot be avoided.** Four
packages need a decision; they are the first four sections below.

## Direct runtime dependencies — verified

| Package | Declared spec | Resolved | License |
|---|---|---|---|
| `azure-identity` | `~=1.25.0` | 1.25.3 | MIT |
| `azure-mgmt-compute` | `~=37.2.0` | 37.2.0 | MIT |
| `azure-mgmt-monitor` | `~=7.0.0` | 7.0.0 | MIT |
| `azure-mgmt-network` | `~=30.2.0` | 30.2.0 | MIT |
| `azure-mgmt-resource` | `~=25.0.0` | 25.0.0 | MIT |
| `azure-mgmt-storage` | `~=24.0.0` | 24.0.1 | MIT |
| `azure-monitor-query` | `~=1.4.0` | 1.4.1 | MIT |
| `boto3` | `~=1.42.0` | 1.42.97 | Apache-2.0 |
| `cachehash` | **undeclared** | 1.1.4 | **CC-BY-NC-4.0** |
| `defusedxml` | `~=0.7.1` | 0.7.1 | PSFL |
| `gemfileparser` | `~=0.8.0` | 0.8.0 | **GPL-3.0-or-later OR MIT** |
| `google-cloud-compute` | `>=1.14.0` | 1.54.0 | Apache-2.0 |
| `google-cloud-monitoring` | `>=2.15.0` | 2.31.0 | Apache-2.0 |
| `google-cloud-storage` | `>=2.10.0` | 3.14.1 | Apache-2.0 |
| `httpx[http2]` | `~=0.28.1` | 0.28.1 | BSD-3-Clause |
| `Jinja2` | `==3.1.6` | 3.1.6 | BSD-3-Clause |
| `johnnydep` | `~=1.20.6` | 1.20.6 | MIT |
| `modernmetric` | `>=1.5.9` | 1.5.9 | **CC-BY-NC-4.0** |
| `psutil` | `~=7.2.0` | 7.2.2 | BSD-3-Clause |
| `pygments-tsx` | `>=1.0.1` | 1.0.4 | **CC-BY-NC-ND-4.0** |
| `PyYAML` | `~=6.0.2` | 6.0.3 | MIT |
| `semgrep` | `==1.152.0` | 1.152.0 | **LGPL-2.1-or-later** |
| `tomli` | `; python_version < '3.11'` | — | *marker can never fire* |
| `windows-curses` | `; sys_platform == 'win32'` | — | *only needed by an accidental import* |

Dev extras — `black` (MIT), `pytest` (MIT), `pytest-cov` (MIT),
`pytest-xdist` (MIT), `coverage` (Apache-2.0). No concerns.

---

## 1. Semgrep — LGPL-2.1-or-later, imported in-process

The most consequential finding in this review, for two independent reasons.

**Licensing.** `semgrep` is **LGPL-2.1-or-later**. VerinFast imports it
*in-process* — `code_scan.py` does `import semgrep.commands.scan as
semgrep_scan`, calls `semgrep_scan.scan(custom_args)` and catches the
`SystemExit` that comes back. LGPL's reciprocity turns on linking, and the
in-process import is the most aggressive reading of that boundary; running the
same binary as a **subprocess** is the posture nobody argues about.

[[Feature: Security Scan (Semgrep)]] already calls for subprocessing it for a
different reason — `SystemExit` escaping into ATD v3's worker
([[Requirements: Embeddable Library API]] `L6`). The licensing question makes
the same change the conservative choice as well. **That is a happy coincidence,
not legal advice** — see the action items.

Two related notes:

- **`--config auto` is the bigger licensing exposure, and subprocessing the
  engine does nothing for it.** The rules are licensed separately from the
  engine: since 2024-12-13, Semgrep-maintained registry rules are under the
  **Semgrep Rules License v1.0**, which permits use *"only for your own
  internal business purposes"* and not *"to make them available to others as a
  service"*. VerinFast is a commercial diligence product heading into a hosted
  one. This applies to the agent **as it ships today**, not just to v2. Fully
  worked through, with alternatives, in [[Semgrep Alternatives]].
- The 1.152.0 wheel ships **no LICENSE file** in its dist-info; the LGPL
  declaration is in the metadata only. If VerinFast redistributes Semgrep in a
  container image, attribution has to come from upstream, not from the wheel.

**Semgrep is also a third of the dependency tree.** Of the 127-package
runtime closure, **44 — 35% — are pulled in by `semgrep` and nothing else**:

> annotated-types, attrs, boltons, bracex, click, click-option-group, colorama,
> exceptiongroup, face, glom, httpx-sse, importlib-metadata, jsonschema,
> jsonschema-specifications, mcp, opentelemetry-\* (11 packages), peewee,
> pydantic, pydantic-core, pydantic-settings, python-dotenv, python-multipart,
> referencing, rpds-py, ruamel.yaml(+clib), semantic-version, sse-starlette,
> starlette, tomli, typing-inspection, uvicorn, wcmatch, wrapt, zipp

Note what that list contains: an **MCP server**, **Starlette**, **Uvicorn** and
a full **OpenTelemetry** stack. Installing VerinFast installs an ASGI web
server. For `S17` ("keep the dependency surface small enough to audit") this is
the single biggest lever available.

**Decision: CHANGE the integration, and re-examine the engine.** Run the
scanner as a subprocess against a pinned version, and take it out of the base
install. That takes the default runtime footprint from **127 packages to 82**
and moves the LGPL boundary to a process call.

On the engine itself, [[Semgrep Alternatives]] recommends **Opengrep** — the
LGPL-2.1 community fork, rule- and output-compatible, governed by a vendor
consortium, and distributed as a binary rather than a PyPI package, which
deletes those 44 packages outright instead of relocating them. Semgrep CE
remains a working fallback; the engine licence is fine either way. **The
ruleset has to change regardless of which engine runs it.**

## 2. `pygments-tsx` — CC BY-NC-**ND**-4.0 (first-party)

`pygments-tsx` is VerinFast's own package (`github.com/StartupOS/pygments_tsx`),
licensed **CC BY-NC-ND 4.0** — Attribution, NonCommercial, **NoDerivatives**.

The **ND** term is the issue. NoDerivatives means nobody may distribute a
modified version — which for a software library is a strange thing to promise,
and it forecloses the ordinary open-source contribution path on a package that
`modernmetric` also depends on. NC alone would be consistent with the rest of
the family; ND is an extra restriction that looks unintentional.

Because it is first-party, this is a **relicensing decision, not a replacement**.

**Decision: KEEP. Raise the ND term with the owner.**

## 3. `gemfileparser` — dual GPL-3.0-or-later **OR** MIT

The wheel ships both `LICENSE.GPLv3` and `LICENSE.MIT`. A dual license is a
choice, and the choice must be made and recorded — an unrecorded dual license
reads as "GPL" to the next auditor.

**Decision: KEEP, electing MIT.** Record the election in `pyproject.toml` and
in the distributed attribution notice.

## 4. `chardet` — LGPL-2.1-or-later (transitive)

Arrives via `modernmetric` and `pygount`. Same LGPL family as Semgrep, but a
pure-Python library imported in-process, and the importer is first-party. Lower
stakes, same question.

**Decision: KEEP, and fold into the same legal review as Semgrep.** If the
answer there is "in-process LGPL import is unacceptable", `pygount` is the
thing to look at, since that is what drags `chardet` in.

## 5. MPL-2.0 — `certifi`, `pathspec`

`certifi` (via `httpx`/`requests`) and `pathspec` (via `black`, dev-only).
MPL-2.0 is file-level copyleft: it reaches modifications to *those files*, not
to the program that uses them. Neither is modified.

**Decision: KEEP. No action.**

---

## Keep / replace / drop

### Keep unchanged

`httpx[http2]`, `PyYAML`, `psutil`, `defusedxml`, `Jinja2` (but see
*Pinning*), and the whole permissive transitive tree.

### Keep, behind optional extras

The eleven cloud SDKs — **7 Azure (MIT), `boto3` (Apache-2.0), 3 Google
(Apache-2.0)** — are all permissively licensed and all worth keeping. But a
customer who only wants a code scan currently installs three cloud SDK
families. Split into `verinfast[aws]`, `[azure]`, `[gcp]`, `[cloud]`.

Exclusive subtree sizes, for sizing the win: `boto3` → 5 packages,
`google-cloud-storage` → 3, `azure-identity` → 2.

### Replace the integration, not the package

| Package | Change |
|---|---|
| `semgrep` | subprocess instead of in-process import; optional extra (§1) |
| `boto3` | **expand** its use — it already ships, so the AWS CLI shell-out in `cloud/aws/costs.py` can go, which also removes a `shell=True` with an interpolated profile name (`S9`, `D9`) |

### Evaluate for replacement

**`johnnydep`** (MIT, 9 exclusive packages: anytree, cachetools, oyaml, pip,
structlog, tabulate, toml, wheel, wimpy). It resolves Python dependencies by
querying PyPI and downloading wheels. Under `S8` ("prefer lockfile parsing over
installation") v2 wants lockfile-first resolution, which is most of what
johnnydep is doing the expensive way. Note it also vendors `pip` as a runtime
dependency.

*Not a licensing concern — a footprint and behaviour one.* Decide alongside
[[Feature: Dependency & License Inventory]].

### Drop

| Package | Why |
|---|---|
| `tomli` | declared `; python_version < '3.11'` while `requires-python` is `>=3.11` — **the marker can never fire**. Dead declaration. (It still installs, because Semgrep needs it.) |
| `windows-curses` | only required because `walkers/npm.py` does `from curses.ascii import isdigit` for a one-line digit check (`D12`, `N2`). Remove the import, remove the dependency. |
| `semgrep==1.136.0 ; python_version == '3.9'` | second dead marker — 3.9 is below the floor. |

### Declare

**`cachehash` is imported by `agent.py` and `code_scan.py` but is not in
`pyproject.toml`** (`D11`, `N3`). It resolves today only because
`modernmetric>=1.5.9` happens to require `cachehash>=1.1.4`. A modernmetric
release that drops it turns `pip install verinfast` into an ImportError at
startup. It is first-party (`github.com/VerinFast/cachehash`, CC BY-NC 4.0), so
this is a one-line fix — but [[Feature: Scan Caching]] also questions whether
the cache survives v2 at all, so declare it or drop it, not neither.

### Pinning

`Jinja2==3.1.6` and `semgrep==1.152.0` are hard `==` pins; everything else is
`~=` or `>=`. A hard pin on a transitive-heavy package like Semgrep is
defensible (it is a scanner whose output must be reproducible); a hard pin on
Jinja2 mostly blocks security updates. **Recommend:** keep Semgrep pinned and
record *why* next to the pin; relax Jinja2 to `~=3.1`.

---

## VerinFast's own license — a decision for workstream 5

VerinFast ships **Creative Commons Attribution-NonCommercial 4.0** (`LICENSE`),
and `pyproject.toml` classifies as *"Free for non-commercial use"*. The
first-party dependencies are consistent with it: `modernmetric` CC BY-NC-4.0,
`cachehash` CC BY-NC-4.0, `pygments-tsx` CC BY-NC-ND-4.0.

Two things are worth raising before v2 locks this in:

1. **Creative Commons licenses are not designed for software.** Creative
   Commons says so themselves and recommends a software license instead. They
   have no patent grant, no source-availability mechanics, and no
   well-understood notion of linking or derivative works *for code* — which is
   precisely the question §1 and §4 of this page turn on.
2. **The NC term interacts awkwardly with [[Requirements: Embeddable Library
   API]].** Workstream 5 makes VerinFast importable into ATD v3, a hosted
   commercial service. VerinFast owns the copyright, so it can license its own
   code to itself — but an NC license tells *every other reader* that the
   commercial use they can see happening is not available to them, which is an
   odd signal for a repository described as "An open sourced scanning agent".

**Not a blocker, and not a call this review makes.** It belongs in
[[Open Questions]] as a new entry — proposed **Q11** — to be added when this
page and the rest of the wiki meet on `main`.

---

## Action items

| # | Action | Requirement |
|---|---|---|
| 1 | Run Semgrep as a subprocess; move it out of the base install | `L6`, `S17` |
| 2 | Get legal confirmation on in-process LGPL imports (Semgrep, `chardet`) | `S16` |
| 3 | Pin/record the Semgrep ruleset version in the findings artifact | `S18` |
| 3a | **Replace `--config auto` with a pinned, explicitly-licensed ruleset** — see [[Semgrep Alternatives]] | `S18` |
| 4 | Elect **MIT** for `gemfileparser` and record the election | `S16` |
| 5 | Raise the **ND** term on `pygments-tsx` with its owner | `S16` |
| 6 | Declare `cachehash` — or drop it with the cache | `N3`, `D11` |
| 7 | Split cloud SDKs into `[aws]` / `[azure]` / `[gcp]` extras | `S17` |
| 8 | Delete the two dead environment markers (`tomli`, `semgrep` py3.9) | `N3` |
| 9 | Remove the `curses.ascii` import, then drop `windows-curses` | `N2`, `D12` |
| 10 | Replace the AWS CLI shell-out with `boto3` | `S9`, `D9` |
| 11 | Evaluate replacing `johnnydep` with lockfile-first resolution | `S8` |
| 12 | Relax `Jinja2==3.1.6` to `~=3.1`; document why Semgrep stays pinned | `S16` |
| 13 | Ship an attribution notice (NOTICE / THIRD-PARTY-LICENSES) generated from installed metadata | `S16` |
| 14 | Decide VerinFast's own license before workstream 5 lands | proposed Q11 |

Items 1, 7, 8, 9 and 10 are the ones that change the architecture, so they
belong to workstream 3 rather than here.

## Related

[[Semgrep Alternatives]] · [[Feature: Dependency & License Inventory]] · [[Requirements: Security & Privacy]] · [[Known Defects & Debt]] · [[v2 Workstreams]]
