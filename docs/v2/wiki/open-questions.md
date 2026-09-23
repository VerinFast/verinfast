---
title: Open Questions
parent: verinfast-v2
status: needs decisions
tags: v2, decisions
---

# Open Questions

Decisions needed before workstream 3 (folder structure) can start. Each blocks
something concrete.

## Q1 — Isolation model for untrusted samples

ATD v3 will scan code samples it does not trust. Options:

1. **In-process** — fastest, simplest; a hostile file or a scanner crash takes
   down the worker.
2. **Subprocess per scan** — the library spawns a child it can kill and time
   out. Costs startup latency; needs a serialisation boundary for `ScanResult`.
3. **Container per scan** — ATD's problem, not ours, but changes what the
   library API should look like.

*Blocks:* L10, L11, S11, and the shape of the public API.
**Recommendation:** design for (2) as the library default, and let ATD choose
(3) around it.

## Q2 — Result model: pydantic or dataclasses?

ATD v3 is pydantic v2 throughout, and a pydantic `ScanResult` would drop
straight into its ingest services. But it adds a heavyweight dependency to a
tool that is installed on customer laptops.

*Blocks:* L2, L13.
**Recommendation:** pydantic. It is already transitively present via several
dependencies, and matching the consumer's idiom is worth more than the
kilobytes.

## Q3 — Sync or async public API?

ATD v3 is FastAPI + async SQLAlchemy. A multi-minute blocking call is
unusable on its event loop.

*Blocks:* L11.
**Recommendation:** a sync core with a thin documented `async` wrapper, rather
than an async core — the work is subprocess-bound, not I/O-concurrency-bound.

## Q4 — Per-file line ceiling

good-place enforces a "<500 lines" rule on folded code. Adopt the same number
here, or a different one?

*Blocks:* N6, and therefore the whole module decomposition.
**Recommendation:** adopt 500, for consistency with the consumer repo.

## Q5 — Is `git_metrics.py` a feature or dead code?

`utils/git_metrics.py` computes per-commit, per-file modernmetric deltas and is
called from nowhere. ATD v3 has `developerimpact` and `dailydeveloperimpact`
widgets that would want exactly this.

*Blocks:* whether v2 ports it, finishes it, or deletes it.

## Q6 — Does `system_info.json` get uploaded?

It is produced and never sent; ATD has no route for it. Either add a route on
the ATD side or stop producing it. It contains the hostname, so uploading it
has a privacy dimension.

## Q7 — Fix or preserve the `signed` semantics?

`formatGitHash` treats every `%G?` value except a bare `N` as "signed", and the
value is quote-wrapped by the literal format string, so it is effectively
always `True`. ATD stores a boolean. Fixing it changes historical data
comparability.

## Q8 — Prove or replace the Semgrep cache key

`cache.get(path)` is keyed on a path that is identical for every cloned repo
(`~/.verinfast/temp_repo`). Whether that is safe depends on `cachehash`
internals. Needs a test that scans two different repos in one run and asserts
the findings differ.

*Blocks:* whether the cache survives into v2 at all.

## Q9 — Default truncation on?

ATD v3 configures `truncate_findings: true` by default. The agent defaults it
off. Given the threat model, should v2 default it on?

## Q10 — What happens to the telemetry endpoint?

`logger.verinfast.com` is called on every run. Keep it (documented and
consent-covered), keep it only for CLI use, or drop it?

*Blocks:* S4, L9.

## Q11 — What licence does VerinFast v2 ship under?

`pyproject.toml` declares **CC BY-NC 4.0**. It is a content licence applied to
code: no patent grant, no source-availability mechanics, and no settled notion
of linking or derivative works for software. The **NC** term also sits oddly
against [[Requirements: Embeddable Library API]] — workstream 5 imports
VerinFast into ATD v3, a hosted commercial service. VerinFast owns its own
copyright so it can licence to itself, but every other reader is told the
commercial use they can see happening is not available to them, in a repository
described as "an open sourced scanning agent".

*Raised by:* [[Dependency & License Review]] § *VerinFast's own licence*.

*Blocks:* workstream 5 shipping publicly. Not the review's call to make.

## Q12 — Legal sign-off on the scanning ruleset

Two questions, and they are separate:

1. **The agent as it ships today.** `--config auto` pulls the Semgrep registry
   at scan time. Since 2024-12-13 those rules carry the **Semgrep Rules License
   v1.0**: internal use only, non-competing, not as part of a SaaS. Running
   them inside a customer perimeter on behalf of a vendor is at least worth a
   look. Subprocessing the engine does nothing about this — it is the *rules*,
   not the engine.
2. **The ruleset v2 ships instead.** `elttam/semgrep-rules` and
   `0xdea/semgrep-rules` are both MIT, and the vendored copies carry their
   upstream LICENSE files and a per-file manifest. `scripts/sync_rules.py`
   enforces the policy mechanically — an allow-list of licences and a
   forbidden-phrase check that rejects NonCommercial, Commons Clause and the
   GNU family — so the claim is proven by construction rather than asserted.
   Counsel still needs to confirm the posture, including redistribution inside
   ATD v3.

*Raised by:* [[Semgrep Alternatives]] § *Recommendation*.

*Blocks:* nothing technically — the ruleset has landed. It blocks being
comfortable about it.
