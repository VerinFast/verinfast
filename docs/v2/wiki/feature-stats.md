---
title: Feature: Code Statistics (Modernmetric)
parent: features
artifact: {repo}.stats.json
route: stats
tags: v2, feature, code
---

# Feature: Code Statistics (Modernmetric)

## What it produces

Modernmetric's native JSON:

```
{"files": {"<path>": {code_loc, comment_ratio, cyclomatic_complexity,
                      halstead_*, maintainability_index,
                      operands_*/operators_*, fanout_*, tiobe_*, lang: [...]}},
 "overall": {...same keys...},
 "stats": {"max": {...}, "mean": {...}, "median": {...}, "min": {...}, "sd": {...}}}
```

ATD v3 merges `files.*` onto `report_code_file` rows by path, copies `overall.*`
onto the repository, and flattens `stats.<agg>.<prop>` into
`repository.<agg>_<prop>`.

## How v1 does it

`src/verinfast/agent.py::parseRepo` calls `modernmetric.__main__.main()`
in-process with `--file=<filelist> --output=<stats file>` and a
`license_identifier`. `pygments_tsx.patch_pygments()` is called at **import
time** of `agent.py` to teach Pygments about `.tsx`.

A second, unused-in-the-main-flow module — `utils/git_metrics.py` — calls
modernmetric's `process_diff_content` to compute per-commit, per-file metrics
from a diff. Nothing in `agent.py` calls it. It is either dead code or the
half-built input to ATD's `developerimpact` / `dailydeveloperimpact` widgets;
decide in [[Open Questions]].

## Path rewriting

The agent clones into `~/.verinfast/temp_repo`, so every path in the artifact
is absolute-ish and contains `temp_repo/`. ATD v3 rewrites anything containing
that segment to start with `./`. **v2 should emit repo-relative paths directly**
and let ATD's rewrite become a no-op — but must not *break* it, since older
agents are still in the field.

## What v2 must keep

- The three-block shape, and tolerance for modernmetric adding metric keys
  (ATD drops unknown keys rather than erroring).
- `.tsx` lexer support (`pygments-tsx`).

## What v2 must change

- **Calling another tool's `__main__.main()` is not an API.** Same objection as
  [[Feature: Security Scan (Semgrep)]]: in library mode a `SystemExit` or a
  `sys.argv` assumption inside a vendored entry point becomes ATD v3's problem.
- Patching Pygments as an import side effect must move behind an explicit call.

## Related

[[Feature: File Inventory & Sizes]] · [[Requirements: Embeddable Library API]]
