---
title: Semgrep Alternatives
parent: dependency-review
workstream: 2
status: recommendation — needs legal sign-off
verified: 2026-09-23
tags: v2, licensing, dependencies, security
---

# Semgrep Alternatives

Follow-on to [[Dependency & License Review]] §1.

## The finding that reframes this

The review flagged that Semgrep's **engine** is LGPL-2.1-or-later and that we
import it in-process. That is real, and the fix (subprocess it) still stands.

But the engine was never the sharp edge. **The rules are.**

`code_scan.py:44` runs Semgrep with `--config auto`, which fetches rules from
the Semgrep Registry at scan time. Since **13 December 2024**, rules authored
and maintained by Semgrep are licensed under the **Semgrep Rules License
v1.0**, which grants use *"only for your own internal business purposes"* and
*"does not allow you to distribute the rules, or to make them available to
others as a service."* Semgrep's own summary is that the rules are available
for **internal, non-competing, non-SaaS** contexts, and that vendors using
them in competing products or SaaS offerings are affected.

VerinFast is a commercial technical-diligence product, and
[[Requirements: Embeddable Library API]] puts it inside ATD v3 — a hosted
service. Both halves of that sentence are what the rules license names.

Two consequences:

1. **This is a question about the agent as it ships today**, not only about
   v2. Every `--config auto` scan pulls those rules.
2. It is **not resolved by subprocessing the engine.** Engine and rules are
   licensed separately; the process boundary does nothing for the rules.

> **Not legal advice.** Everything below is licence text read from the
> source, with citations. Whether any particular use is permitted is a
> question for counsel — see [[Open Questions]], proposed **Q12**.

## Split the decision in two

Replacing "Semgrep" is really two independent choices.

| Layer | What it is | Today |
|---|---|---|
| **Engine** | the pattern-matching runtime | `semgrep` 1.152.0 (pinned), LGPL-2.1-or-later |
| **Rules** | the security content it runs | Semgrep Registry via `--config auto`, Semgrep Rules License v1.0 |

The engine is the easy half. The rules are the half that matters.

## Engines

| Engine | Version | License | Distribution | Verdict |
|---|---|---|---|---|
| **Semgrep CE** | 1.177.0 | LGPL-2.1-or-later | PyPI, 27 direct deps | works; keeps us in the registry's orbit |
| **Opengrep** | 1.27.1 | LGPL-2.1 | **not on PyPI** — native binary, install script, Docker | **recommended** |
| **ast-grep** | 0.45.3 | MIT | PyPI (`ast-grep-cli`), **0 deps** | structural search, *not* a security scanner |

### Opengrep

A community fork of Semgrep CE created in early 2025, specifically in response
to the December 2024 rules relicensing. Maintained by a consortium of appsec
vendors (Aikido, Endor Labs, Jit, Orca and others) with a full-time OCaml
team, so no single vendor owns the roadmap.

Why it fits VerinFast unusually well:

- **Rule-format compatible.** Existing Semgrep rules and rulesets run
  unchanged, and it emits JSON and SARIF — so
  [[ATD v3 Upload Contract]]'s findings ingest, which models native
  `semgrep --json`, needs checking but is very likely unaffected. That is the
  single biggest reason to prefer a fork over a different tool.
- **It is a binary, not a library.** Opengrep is not on PyPI (verified:
  `https://pypi.org/pypi/opengrep/json` → **404**, as are `opengrep-cli`,
  `opengrep-core`, `pyopengrep`). It installs via script, Docker, or a signed
  release binary. That sounds like a drawback and is actually the point — it
  *forces* the subprocess architecture [[Feature: Security Scan (Semgrep)]]
  already wants, and it removes all **44 Semgrep-exclusive PyPI packages**
  outright rather than hiding them behind an extra. Runtime closure goes from
  127 packages to 82 with no optional-install caveat.
- **More analysis, not less.** The fork restored taint analysis,
  inter-procedural scanning, fingerprinting and Windows support that CE had
  dropped. Windows support in particular is interesting: `run_scan` currently
  bails out entirely on Windows.
- 30+ languages, taint tracking across 12.

The cost: **Opengrep ships no ruleset of its own.** Sourcing and maintaining
rules becomes ours. See below — that is unavoidable either way.

### ast-grep

MIT, Rust, zero Python dependencies, and genuinely excellent at structural
search and rewrite. But it is a *code search* tool, not a security scanner:
there is no curated vulnerability ruleset behind it. Adopting it would mean
authoring VerinFast's entire security corpus from scratch. **Not a
replacement.** Worth remembering if v2 ever wants cheap structural queries
that aren't security findings.

## Rules — the part that actually needs deciding

| Ruleset | License | Usable in a commercial hosted product? |
|---|---|---|
| `semgrep/semgrep-rules` (what `--config auto` serves) | **Semgrep Rules License v1.0** | **No** — internal only, explicitly not as a service |
| `opengrep/opengrep-rules` (fork of the 2024-12-13 snapshot) | **LGPL-2.1 + Commons Clause** | **Unclear** — Commons Clause forbids "Selling" |
| `0xdea/semgrep-rules` | **MIT** | Yes |
| `elttam/semgrep-rules` | **MIT** | Yes |
| `trailofbits/semgrep-rules` | **AGPL-3.0** | **Careful** — network copyleft, and ATD v3 is a network service |

Two things worth spelling out, because both are easy to get wrong:

- **The Opengrep ruleset is not unencumbered.** It is the last snapshot taken
  *before* the relicense, and that snapshot was LGPL-2.1 **with the Commons
  Clause** — which withholds "the right to Sell the Software", where *Sell*
  means providing a product or service whose value derives substantially from
  the software's functionality. Forking the engine solved the engine problem;
  it did not hand anyone an unrestricted rule corpus.
- **AGPL rules are the riskiest option**, not the safest, precisely because
  ATD v3 is a hosted service. The network clause is the whole point of AGPL.

The clean answer is the MIT-licensed community sets, plus rules VerinFast
writes and owns. That is a smaller corpus than the registry, and shrinking
coverage is a real product cost — but it is the only column above with an
unambiguous "yes".

## Language-specific scanners — complements, not replacements

None of these replaces a multi-language engine. They are worth knowing about
because a targeted scanner usually beats a generic rule on its own language,
and several are permissively licensed with small footprints.

| Tool | Scope | License | On PyPI | Deps |
|---|---|---|---|---|
| **Bandit** | Python | **Apache-2.0** | `bandit` 1.9.4 | 17 |
| **detect-secrets** (Yelp) | secrets | **Apache-2.0** | `detect-secrets` 1.5.0 | 4 |
| **checkov** | IaC / Terraform | **Apache-2.0** | `checkov` 3.3.19 | 52 |
| **njsscan** | JS / Node | **LGPL-3.0-or-later** | `njsscan` 1.0.1 | 6 |
| **gosec** | Go | Apache-2.0 | no — Go binary | — |
| **DevSkim** (Microsoft) | multi | MIT | **no — see warning** | — |

> ⚠️ **Supply-chain note.** The PyPI project named **`devskim` is not
> Microsoft's DevSkim.** `devskim` 0.8.0 on PyPI is an unrelated
> "Hacker News + Reddit + lobste.rs terminal feed viewer". If DevSkim is ever
> wanted, it is a .NET tool from its own releases — do not `pip install
> devskim`. Verified 2026-09-23.

Similarly, `trufflehog` on PyPI is the abandoned 2.x Python line; current
TruffleHog is a Go program. Name-matching a PyPI package to a known tool is
exactly the mistake VerinFast's own dependency scanner exists to catch.

## Recommendation

1. **Stop using `--config auto`.** It is the live licensing exposure and it
   also makes scans irreproducible ([[Requirements: Security & Privacy]]
   `S18`). Pin an explicit ruleset.
2. **Move the engine to Opengrep**, run as a subprocess. It is
   rule-compatible, output-compatible, consortium-governed, unentangled from
   the rules licence, and being a binary it deletes 44 packages from the
   runtime closure instead of relocating them.
3. **Build the ruleset from the MIT sets plus VerinFast's own rules.**
   Version it, ship it with the agent, and record the resolved ruleset
   version in the findings artifact.
4. **Get counsel to confirm** the current `--config auto` posture and whichever
   ruleset is chosen. Proposed **Q12**.
5. **Keep Semgrep CE as the fallback** if Opengrep's binary distribution turns
   out to be a problem for how VerinFast is shipped. The engine licence
   (LGPL-2.1) is fine either way; it is the rules that must change regardless
   of which engine runs them.

Steps 1 and 3 are worth doing **before** v2, because they apply to the agent
as it ships today.

## Action items

Extends [[Dependency & License Review]]'s list.

| # | Action | Requirement |
|---|---|---|
| 15 | Replace `--config auto` with a pinned, explicitly-licensed ruleset | `S18` |
| 16 | Legal review of the rules licence for the current agent **and** for ATD v3 | `S16`, proposed Q12 |
| 17 | Prototype Opengrep as a subprocess; diff its JSON against Semgrep's on a fixture repo to confirm the ATD ingest contract holds | `A6`, `L6` |
| 18 | Assemble and version a VerinFast ruleset from MIT sources + own rules | `S18` |
| 19 | Decide how a native binary is shipped (vendored, fetched-and-verified, or Docker-only) | `N4` |

## Sources

- [Opengrep](https://github.com/opengrep/opengrep) · [opengrep-rules](https://github.com/opengrep/opengrep-rules)
- [Semgrep Rules License v1.0](https://semgrep.dev/legal/rules-license/) · [semgrep-rules](https://github.com/semgrep/semgrep-rules) · [Important updates to Semgrep OSS](https://semgrep.dev/blog/2024/important-updates-to-semgrep-oss/)
- [What's going on with (Sem|open)grep? — Josh Grossman](https://joshcgrossman.com/2025/01/28/whats-going-on-with-sem-open-grep/) · [Socket: Opengrep emerges](https://socket.dev/blog/opengrep-forks-semgrep) · [InfoQ](https://www.infoq.com/news/2025/02/semgrep-forked-opengrep)
- [Endor Labs: everything about Opengrep](https://www.endorlabs.com/learn/everything-you-need-to-know-about-opengrep) · [Aikido: Opengrep after one year](https://www.aikido.dev/blog/opengrep-sast-one-year)
- Package metadata and licence files read from PyPI and raw.githubusercontent.com on 2026-09-23.

## Related

[[Dependency & License Review]] · [[Feature: Security Scan (Semgrep)]] · [[ATD v3 Upload Contract]] · [[Requirements: Security & Privacy]]
