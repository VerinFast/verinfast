# dependencies/ — Claude notes

- **Never run a package manager.** No `npm install`, no `composer install`,
  no `gem install`, no johnnydep resolution. All of them execute code from
  the scanned project's dependency graph (`S7`, `S8`). A test monkeypatches
  `subprocess` to fail if anything starts one.
- **Parsers are pure `(text, path) -> list[Entry]`.** No I/O, no network, no
  subprocess. That is what keeps them testable from a string and the suite
  offline. Enrichment happens above them, in `walk.py`.
- **A parser never raises.** Malformed input from someone else's repository
  is expected, not exceptional; one bad `pom.xml` must not cost the other
  eight ecosystems.
- **Use `defusedxml`, never `xml.etree` directly** — a pom is untrusted
  input (`S13`). And never call `defusedxml.defuse_stdlib()`: it patches the
  stdlib process-wide, which a library must not do to its host (`D30`, `L2`).
- **An unknown licence is an absent key**, not `"License not available"`.
  ATD stores what it is sent.
- **Every registry call needs a timeout and a failure budget.** There is one
  request per dependency.
- **Lockfile beats manifest, per directory.** A monorepo's packages each have
  their own; a repo-wide preference reports the wrong thing.
- **Specifiers are verbatim.** Do not normalise `^1.2` into `>=1.2,<2` on the
  way out — except for Poetry, where the conversion happens at parse time
  because `^` is Poetry-specific syntax ATD cannot interpret.
- Adding an ecosystem: write the parser, add it to `parsers/MANIFESTS` (or
  `SUFFIXES`), add a `PREFERRED_OVER` entry if it has a lockfile, and wire a
  registry lookup in `walk._LOOKUPS` only if one exists.
