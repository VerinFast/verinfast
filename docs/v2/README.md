# docs/v2/ — the VerinFast v2 design record

A [Waikiki](https://github.com/VerinFast/waikiki) wiki covering workstream 1 of
the v2 rewrite: **features, goals and requirements**.

| File | What it is |
|---|---|
| `wiki/*.md` | The pages. Plain markdown with frontmatter — this is the source of truth, and what you review in a PR. |
| `build_wiki.py` | Compiles `wiki/` into a Waikiki `.wiki` file. |
| `VerinFast-v2.wiki` | The compiled wiki (a single SQLite database), regenerated from `wiki/`. |

## Reading it

**In Waikiki** — open the app, go to the **Wikis** page (⚙ in the header),
choose *Open wiki file…*, and pick `VerinFast-v2.wiki`. Start at **VerinFast
v2**.

**Without Waikiki** — read `wiki/verinfast-v2.md` and follow the
`[[Wikilinks]]`; each one is the title or slug of another file in the same
folder.

## Rebuilding

```sh
pip install markdown-it-py mdit-py-plugins linkify-it-py pygments
python docs/v2/build_wiki.py                      # → docs/v2/VerinFast-v2.wiki
python docs/v2/build_wiki.py --check-only         # validate wikilinks, build nothing
python docs/v2/build_wiki.py --waikiki ~/src/waikiki   # use Waikiki's own renderer
```

Every build validates wikilinks first and **refuses to build** if any
`[[Wikilink]]` points at a page that does not exist — pass `--allow-broken` to
override. `--check-only` runs just that validation and exits non-zero on a
broken link, which makes it usable as a pre-commit or CI check.

The build writes to a sibling temp file and swaps it in only on success, so a
failed rebuild leaves the previous `.wiki` intact.

## Page frontmatter

```
---
title: Feature Inventory      # page title; defaults to the filename
parent: verinfast-v2          # slug of the parent page (the filename, minus .md)
tags: v2, features            # comma-separated; Waikiki indexes these
---
```

Any other `key: value` line is rendered by Waikiki as an infobox row, which is
how pages carry things like `artifact:`, `route:` and `status:`.

## Where the content came from

Everything was derived by reading `VerinFast/verinfast@ea5ad24` and
`VerinFast/good-place@74e41ff` (`services/atd`). Claims about the ATD v3 upload
contract come from that service's routes and its own agent-contract test, not
from memory.
