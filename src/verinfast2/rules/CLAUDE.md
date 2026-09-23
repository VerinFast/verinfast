# rules/ — Claude notes

- **Generated. Never hand-edit a file here**, and never add one. Change
  `scripts/sync_rules.py` and re-run it. `--check` verifies the tree against
  the pins, but it clones the upstreams, so it is a manual or scheduled check
  — **not** part of the CI run, which is offline by design (`N16`). The
  offline invariants (unique ids, no duplicate bodies, no fixtures, licences
  recorded) are covered by `tests/v2/test_ruleset.py` instead.
- **Rule files are copied byte for byte. Never re-serialise them.** An
  earlier version of the sync script parsed each file and dumped it back
  out, which silently broke `elttam/rules/generic/jsp-likely-xss.yaml`: YAML
  1.1 treats a bare `on` as a boolean, so PyYAML read the join rule's `on:`
  condition key as `True` and wrote it back as `true:`. The engine reads `on`
  as a string, saw a join block with no conditions, and crashed with
  `reduce() of empty iterable`. Round-tripping YAML you do not own is a class
  of bug — parse to *analyse*, never to rewrite.
- **Never `--config auto`.** Registry rules are licensed for internal,
  non-competing, non-SaaS use only. That is the reason this directory exists.
- **Pins are commits, never branches.** A scan has to be reproducible, and
  "whatever main said that day" is not a pin.
- **Refuse a source with no LICENSE file.** `sync_rules.py` already does;
  don't add an override.
- **Test fixtures are excluded on purpose.** Both upstreams keep
  deliberately-vulnerable sample code beside the rules that match it.
  Shipping it would put exploit code in the agent and make it scan itself.
- **Deduplicate by id *and* by normalised body.** A duplicate id is fatal to
  the engine; duplicate logic under two names just doubles every finding.
  Both land in `MANIFEST.json`'s `exclude` list rather than being edited out.
- Record `Ruleset.provenance` in the findings artifact. A finding set nobody
  can attribute to a rule revision is not explainable six months later.
- Build the engine's environment with `ruleset.engine_env()`. Opengrep's
  bundled interpreter picks its encoding from the locale and dies with
  `UnicodeDecodeError: 'ascii' codec` on a container with no `LANG`.
