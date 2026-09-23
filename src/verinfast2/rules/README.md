# rules/

The security rules VerinFast ships. **Generated — do not edit by hand.**

Written by `scripts/sync_rules.py` from MIT-licensed upstreams pinned to a
revision. `MANIFEST.json` records where every rule came from.

| Source | Licence | Rules | Covers |
| ------ | ------- | ----- | ------ |
| [elttam/semgrep-rules](https://github.com/elttam/semgrep-rules) | MIT | 107 | Go, Java, JS/TS, YAML/Kubernetes, generic |
| [0xdea/semgrep-rules](https://github.com/0xdea/semgrep-rules) | MIT | 50 | C, C++, Java |

157 rules in 130 files.

## Why the rules ship instead of being fetched

VerinFast does not use `--config auto`. Rules from the Semgrep Registry are
licensed for **internal, non-competing, non-SaaS** use only — which is not
what a commercial diligence product running inside a hosted service is doing.
Fetching them at scan time also makes a scan irreproducible and requires
outbound network access from inside a customer's perimeter.

Shipping a pinned, MIT-licensed set fixes all three.

## The engine

[Opengrep](https://github.com/opengrep/opengrep) — the LGPL-2.1 community
fork of Semgrep CE. It reads this exact rule format and emits the same JSON,
so the ATD v3 findings contract is unaffected.

Verified on this corpus: Opengrep 1.27.1 loads all 157 rules with **zero**
parse errors. Semgrep 1.152.0 rejects 12 of them (`Invalid pattern for Java`
on annotation-on-class patterns) and consequently misses their findings.

## Updating

```sh
python scripts/sync_rules.py --update   # report each source's HEAD
python scripts/sync_rules.py            # rebuild at the pinned revisions
python scripts/sync_rules.py --check    # verify the tree matches the pins
```

`--check` clones the upstreams, so it needs network and is a manual or
scheduled check rather than a CI step — the test suite stays offline. The
invariants that can be checked without network (unique ids, no duplicate
bodies, no fixtures, licences recorded) live in `tests/v2/test_ruleset.py`.

Files are copied **byte for byte**. See `CLAUDE.md` for why that is not
negotiable.

## Deduplication

Two sources can ship the same rule id, or the same logic under two names —
either way every hit gets reported twice. `sync_rules.py` detects both and
records the losers in `MANIFEST.json`'s `exclude` list, which the scan passes
to the engine as `--exclude-rule`.

The two current sources are disjoint, so that list is empty today. It is
still built and tested, because the next source added may not be.
