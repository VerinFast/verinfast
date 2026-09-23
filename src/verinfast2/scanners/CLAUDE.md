# scanners/ — Claude notes

- **Return, don't raise.** A failure is an `ArtifactResult` with
  `Outcome.FAILED` and an error string. Raising loses the other artifacts
  (`F19`).
- **Never modify the scanned tree.** No `git init`, no branch checkout on a
  local path unless explicitly asked. v1 created `.git` directories in users'
  folders (`D3`, `S12`).
- **Never `os.chdir()`.** `cwd=` on the subprocess (`L4`).
- **Never call another tool's `__main__.main()` or import its CLI.** Semgrep
  and modernmetric both exit the process on completion, so the "return value"
  is a `SystemExit` — which lands in ATD v3's worker (`D18`, `L6`).
- **`--config auto` is not allowed.** It fetches rules whose licence permits
  internal, non-competing, non-SaaS use only, and it makes scans
  irreproducible. Pin a ruleset and record its version in the artifact
  (`S18`). See the wiki's *Semgrep Alternatives*.
- **Package-manager execution is opt-in and refused when `embedded`.**
  `npm install` / `composer install` / `gem install` run arbitrary code from
  the scanned project's dependency graph (`S7`).
- **The wire shapes are fixed by ATD**, not by us: numstat values stay strings
  including `"-"`; sizes keeps its `"."` root entry and four metadata keys;
  stats keeps `overall` and `stats.<agg>.<prop>`; dependencies stays a flat
  array with `name` and `source` required. Changing one needs the matching
  change on the ATD side.
- Adding a scanner: implement the protocol, register it in `base.registry()`,
  add its artifact to `models.Artifact`, and confirm it has an upload route.
