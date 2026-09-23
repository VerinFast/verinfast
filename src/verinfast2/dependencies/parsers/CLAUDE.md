# dependencies/parsers/ — Claude notes

- **Signature is `(text, path) -> list[Entry]`.** Never take a `Path` and
  read it yourself: purity is what keeps these testable from a string and the
  suite offline.
- **Never raise.** Return `[]` on anything malformed. The caller logs a
  warning; one bad file must not cost the other ecosystems.
- **`defusedxml`, never `xml.etree`** — manifests are untrusted input
  (`S13`). Import it inside the function, not at module scope, so importing
  the package does not require it.
- **Specifiers are verbatim**, except Poetry's `^`/`~`, which are converted
  at parse time because ATD cannot interpret them.
- **The odd cases in `README.md` are real and each has a test.** Before
  "simplifying" a regex or a split, read the case it exists for — most of
  them are v1 bugs.
- Adding a format: write the function, add it to `MANIFESTS` or `SUFFIXES`
  in `__init__.py`, and add its odd cases to the README table with tests.
