---
title: Decisions Landed
parent: verinfast-v2
status: living
tags: v2, decisions, record
---

# Decisions Landed

What has actually been decided and merged, as opposed to
[[Open Questions]] (still open) and [[v2 Workstreams]] (still planned). Each
entry names the decision, the reasoning, and where the code lives.

## D-1 — Opengrep replaces Semgrep as the engine

**Decided.** Merged on `main` at `438d291`.

The trigger was licensing, but the decision held on the technical merits too.
[[Semgrep Alternatives]] has the full comparison; the short version:

| | Semgrep CE | **Opengrep** | ast-grep |
|---|---|---|---|
| Engine licence | LGPL-2.1 | LGPL-2.1 | MIT |
| Entangled with the rules licence | yes | no | n/a |
| Runs the chosen rulesets | 12 parse errors | **157 rules, 0 errors** | rejects both |
| Taint / dataflow | yes | yes | **no** |
| Runtime closure | 44 packages | one binary | one binary |
| Telemetry | opt-out, still dials home | **none** | none |

ast-grep was evaluated seriously — MIT and Rust are both attractive — and
**rejected empirically, not on taste**. Its rule format is incompatible, and 12
of the rules are taint-mode, which it structurally cannot express. That is not
a porting exercise; it is a rewrite of the corpus with capability loss.

*Code:* `src/verinfast2/scanners/ruleset.py`. `engine_command()` never emits
`--config auto`. `engine_env()` forces `LANG`/`LC_ALL=C.UTF-8` and
`PYTHONUTF8=1`, because the engine reads rule files with the interpreter's
default encoding and several shipped rules contain typographic punctuation — on
a stock slim image it dies with `UnicodeDecodeError` while *reading a rule*.

## D-2 — The ruleset ships with the agent, vendored and verified

**Decided.** 130 files, 157 rules, ~920 KiB under `src/verinfast2/rules/`.

- `elttam/semgrep-rules` — 107 rules, MIT, rev `2442685`
- `0xdea/semgrep-rules` — 50 rules, MIT, rev `72b78c1`

Dedupe is by rule id and normalised body. The two sets turned out to be
disjoint — **zero collisions** — so the dedupe machinery is load-bearing only
for future sources.

Three things make this more than a copy-paste:

1. **Files are copied byte-for-byte.** The first version of the sync script
   parsed and re-dumped the YAML, which corrupted `jsp-likely-xss.yaml`: YAML
   1.1 reads a bare `on` as boolean, so PyYAML turned the join rule's `on:` key
   into `true:` and the engine died with `reduce() of empty iterable`. Dedupe
   is now expressed as an `exclude` list in `MANIFEST.json`, applied at scan
   time via `--exclude-rule`, so no shipped byte is ever rewritten. There is a
   regression test.
2. **The licence claim is enforced, not asserted.** `verify_license()` checks
   each source's LICENSE text against an allow-list (MIT, Apache-2.0, BSD-3,
   BSD-2) and a forbidden-phrase list (NonCommercial, Commons Clause, GNU
   GENERAL PUBLIC, GNU AFFERO, GNU LESSER). An earlier draft carried a
   docstring saying the licence was "verified from the upstream LICENSE file"
   with nothing doing the verifying — the same over-claim class as the
   embedded-mode docs bug below.
3. **`--check` mode** re-derives the manifest and fails if the tree drifts.

*Code:* `scripts/sync_rules.py`, `src/verinfast2/rules/MANIFEST.json`,
`tests/v2/test_ruleset.py`. `.gitattributes` marks the tree
`linguist-vendored`.

## D-3 — The upload path contract is pinned by test, not by prose

**Decided.** `src/verinfast2/transport/paths.py` is the wire contract with
ATD v3, and `tests/v2/test_upload_paths.py` has 44 cases holding it still.

The golden case:

```
upload_path(UploadConfig(uuid=True), "scan_id", report="9a6e…")
  == "/report/uuid/9a6e…/CodeScan"
```

`DEFAULT_CODE_SEPARATOR` is `/CodeScan` — it changed from the old value in
`main` PR #814 while this wiki was being written, which is why four pages
needed correcting. See [[ATD v3 Upload Contract]].

## D-4 — Embedded mode writes nothing unless told where

**Decided,** and it is a correction. The folder docs originally promised
"embedded mode writes nothing to `~`", while `for_library()` left
`write_files` on and `artifact_path()` would happily `mkdir -p` anywhere.

The suggested remedy — reject paths under `Path.home()` — was **declined**:
containers routinely have `HOME` as the working root, ATD v3's own workers
included, so the guard would fire on exactly the legitimate case. The fix is
that `write_files` is only true when an explicit `output_dir` was given:

```python
def for_library(self) -> ScanConfig:
    return self.model_copy(update={
        "embedded": True,
        "write_files": self.write_files and self.output_dir is not None,
        "privacy": self.privacy.model_copy(
            update={"telemetry": False, "upload_logs": False}),
        "code": self.code.model_copy(
            update={"allow_package_manager_execution": False}),
    })
```

Embedded mode also hard-disables telemetry, log upload, and package-manager
execution. Those are not defaults the caller can flip back on — they are what
`embedded` *means*. Relates to [[Requirements: Embeddable Library API]] and
[[Requirements: Security & Privacy]].

*Code:* `src/verinfast2/config/schema.py`, `tests/v2/test_public_api.py`
(purity checked in a subprocess).

## D-5 — Cleanup failures are logged, never swallowed

**Decided.** `scan_context()` used `shutil.rmtree(ignore_errors=True)`, which
contradicts the package's own N10 rule. A scan work directory that cannot be
removed is a fact the operator needs:

```python
finally:
    if owns:
        try:
            shutil.rmtree(work_dir)
        except OSError as exc:
            ctx.log.warning(
                "could not remove scan work directory %s: %s", work_dir, exc)
```

*Code:* `src/verinfast2/core/context.py`.

## Still open

Nothing here settles [[Open Questions]] Q1 (isolation model) or Q11/Q12
(licensing sign-off). D-1 and D-2 remove the *technical* exposure from
`--config auto`; Q12 is about whether anyone needs to answer for the period
during which it shipped.

## Related

[[Semgrep Alternatives]] · [[Dependency & License Review]] · [[Open Questions]] · [[v2 Workstreams]] · [[ATD v3 Upload Contract]]
