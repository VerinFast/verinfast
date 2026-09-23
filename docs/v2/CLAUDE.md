# docs/v2/ — working notes

## The rule

**Edit `wiki/*.md`. Never edit `VerinFast-v2.wiki`.** It is a compiled
artifact; hand edits are lost on the next build. After changing any page:

```sh
python docs/v2/build_wiki.py                # validates links, then regenerates
```

The build validates wikilinks itself and refuses to write if any is broken, so
a successful build is also a passing link check. `--check-only` runs the
validation alone (for a pre-commit hook or CI); `--allow-broken` forces a build
past a broken link, which you should not need.

Commit both the markdown and the rebuilt `.wiki` in the same commit, or the
two drift.

## Conventions

- **One page per subject.** A fact lives on the page about its subject and is
  referenced elsewhere with `[[Wikilinks]]`, never duplicated.
- **Every page is parented.** Set `parent:` to an existing page's slug, and add
  a link to the new page from that parent, or it is unreachable in the sidebar.
- **Slug = filename.** `feature-semgrep.md` is the slug `feature-semgrep`.
  Wikilinks may use either the slug or the page title.
- **Requirements are MUST / SHOULD / MAY** and carry a stable id (`F1`, `N3`,
  `L7`, `A2`, `S9`). Do not renumber; append.
- **Defects carry a stable id** (`D1`…) and a requirement reference. Same rule.

## Accuracy

Every claim about v1 behaviour must be traceable to a file and, where it is
specific, a line. Every claim about ATD v3 must be traceable to
`VerinFast/good-place` `services/atd`. If you cannot find it in the source,
write the open question on `open-questions.md` instead of asserting.

When a claim is checked against a **newer** revision than the one recorded in a
page's frontmatter, update the frontmatter too.

## Scope

This folder holds workstream 1 (document) and workstream 2 (dependency and
license review, now complete — see `wiki/dependency-review.md` and
`wiki/semgrep-alternatives.md`). It also carries `wiki/decisions.md`, the
record of what has been decided and merged.

It is not a design doc for the implementation — that lives beside the code
under `src/verinfast2/`, one README.md + CLAUDE.md per folder.
