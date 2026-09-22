---
title: Feature: Dependency & License Inventory
parent: features
artifact: {repo}.dependencies.json
route: dependencies
tags: v2, feature, code, licensing
---

# Feature: Dependency & License Inventory

## What it produces

A **flat JSON array** — not a tree — of `Entry` objects:

```
{"name", "source", "specifier"?, "license"?, "summary"?, "required_by"?}
```

`name` and `source` are mandatory (`Entry.__init__` raises otherwise).
`requires` exists on the object but is deliberately **not serialised** —
`Entry.to_json()` omits it. ATD v3 replaces a repo's dependency rows wholesale
on each upload.

## The walkers

`src/verinfast/dependencies/walk.py` runs nine walkers in a fixed order,
rewriting the output file after each one (eight redundant writes) and emitting
`Dependency Scan N%` progress lines.

| Walker | Manifests | How it resolves | Network / shell |
|---|---|---|---|
| `ComposerWalker` | `composer.json` | runs `composer install --no-dev` | **shells out** |
| `MavenWalker` | `pom.xml` | parses XML `<dependencies>` | none |
| `NodeWalker` | `package.json` | runs `npm install --production`, then reads every `node_modules/*/package.json` | **shells out** |
| `PackageWalker` | `package-lock.json` | fallback when `NodeWalker` found nothing; reads licenses from `registry.npmjs.org` | HTTP |
| `NuGetWalker` | `*.csproj` etc. | reads `api.nuget.org` registration + catalog entries | HTTP |
| `GemWalker` | `Gemfile` | runs `gem install --explain`, parses `gemfileparser`, licenses from `rubygems.org` | **shells out** + HTTP |
| `PyWalker` | `requirements*.txt`, `requirements.in`, `Pipfile`, `pyproject.toml`, `poetry.lock` | resolves with `johnnydep` (which queries PyPI) | HTTP |
| `GoWalker` | `go.sum` | pure text parse | none |
| `DockerWalker` | `Dockerfile`, `docker-compose.yml` | parses `FROM` / `image:` lines | none |

Declared-but-unimplemented: Cargo (`Cargo.toml`), and a richer Gemfile parse.

## The trust problem

Three walkers **execute the scanned project's package manager**: `npm install`,
`composer install`, `gem install`. Every one of those runs arbitrary code from
the dependency graph (npm lifecycle scripts, gem extensions) on the scanning
machine.

For a company scanning its own repo on its own laptop that is roughly what they
were going to do anyway. For **ATD v3 scanning an untrusted code sample
in-process** ([[Requirements: Embeddable Library API]]) it is remote code
execution in a service. This is the single biggest architectural constraint on
the rewrite:

> v2 must be able to produce a dependency inventory **without executing the
> scanned project's build tooling**, and installing must be an explicit,
> off-by-default opt-in that library mode refuses outright.

Lockfile-first resolution (`package-lock.json`, `poetry.lock`, `Gemfile.lock`,
`composer.lock`, `go.sum`, `packages.lock.json`) gets most of the way there.

## Other defects

- `npm.py` imports `isdigit` from `curses.ascii` — which is why
  `windows-curses` is a declared dependency of a scanner that never draws a TUI.
- `Walker.initialize()` has signature `(self, command: str)` in the base class
  and `(self, root_path: str)` in `NodeWalker`/`ComposerWalker` — the base is
  never usable polymorphically.
- `Entry` subclasses `dict` but stores everything in instance attributes, so it
  is an empty dict that pretends otherwise.
- Walkers `os.chdir()` into each install point; a failure mid-walk leaves the
  process in the wrong directory.
- `getUrl()` swallows every exception and returns `None`, so a registry outage
  silently produces a license-free inventory rather than a reported gap.

## What v2 must keep

- The flat-array wire shape and the `name`/`source` invariant.
- Coverage of all nine ecosystems — this is the feature customers notice.
- License capture per package, which is the point of the whole module.

## Related

[[Dependency & License Review]] · [[Requirements: Security & Privacy]]
