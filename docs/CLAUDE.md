# docs/ — working notes

- Documentation here describes **intent and contracts**, not implementation
  detail that will drift. If a paragraph would go stale on the next refactor,
  it belongs in a docstring instead.
- Anything asserting behaviour of this codebase or of `VerinFast/good-place`
  must be read out of the source, not recalled. Cite the revision.
- `v2/` is authored as markdown and compiled to a Waikiki `.wiki` file. Edit
  the markdown, then rebuild — never hand-edit the `.wiki`. See
  [`v2/CLAUDE.md`](v2/CLAUDE.md).
