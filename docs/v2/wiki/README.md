# docs/v2/wiki/ — the pages

One markdown file per wiki page. The filename (minus `.md`) is the page slug;
`[[Wikilinks]]` resolve by slug or by title.

Start at [`verinfast-v2.md`](verinfast-v2.md).

| Branch | Pages |
|---|---|
| Top | `verinfast-v2` |
| Goals | `goals` |
| Features | `features` + `feature-*` |
| Requirements | `requirements` + `requirements-*` |
| Reference | `atd-v3-contract`, `current-architecture` |
| Tracking | `known-defects`, `open-questions`, `dependency-review`, `v2-workstreams` |

These files are the source of truth. `../VerinFast-v2.wiki` is built from them
by `../build_wiki.py` — see [`../CLAUDE.md`](../CLAUDE.md).
