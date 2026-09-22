# docs/v2/wiki/ — working notes

Read [`../CLAUDE.md`](../CLAUDE.md) first; it holds the rules that matter
(rebuild after editing, stable requirement/defect ids, traceability).

Specific to this folder:

- **Frontmatter first, then a single `# H1` matching the title.** Waikiki
  renders frontmatter as an infobox above the body.
- **New page checklist:** create the file → set `title`, `parent`, `tags` →
  add a `[[link]]` to it from its parent page → rebuild.
- **Do not restate a feature's implementation in a requirements page**, or
  vice versa. Feature pages describe what v1 does and what v2 must keep or
  change; requirement pages state obligations with ids. Link between them.
- Tables are GFM and render fine in Waikiki; code fences are highlighted.
