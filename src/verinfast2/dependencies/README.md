# dependencies/

The dependency and licence inventory, across nine ecosystems.

| File | What |
| ---- | ---- |
| `models.py` | `Entry` — the row ATD stores |
| `parsers/` | one pure function per manifest format |
| `walk.py` | discover → parse → enrich |
| `registry.py` | the only part that touches the network |

## Three stages, deliberately separable

1. **Discover** — one traversal collecting every file a parser handles.
2. **Parse** — each file through its parser. Pure, offline, never raises.
3. **Enrich** — licences and descriptions the files did not carry.

v1 gave each of its nine walkers its own `rglob("**/*")`, so a monorepo was
walked nine times to find files a single pass sees (`N12`).

## No package manager is ever run

v1's `npm install`, `composer install` and `gem install -r --explain`
execute arbitrary code from the dependency graph of the code being scanned.
That is defensible on a customer's laptop and is remote code execution once
ATD v3 imports us to scan untrusted samples (`S7`, `S8`).

Lockfiles cover the same ground, and better: `package-lock.json`,
`poetry.lock` and `Gemfile.lock` carry **resolved** versions rather than the
ranges a manifest declares. When both sit in one directory, only the lockfile
is parsed — otherwise every package appears twice.

What this costs: a hand-written `requirements.txt` lists only direct
dependencies, so the transitive tail is not reported. v1 resolved it through
johnnydep, which downloads candidate wheels to do so. A `pip-compile` output
or a `poetry.lock` is already complete.

## What leaves the machine

Stage 3 looks up `license` and `summary` from npm, PyPI, RubyGems and NuGet.
**On by default**, matching v1. What goes out is a package name and version,
to that ecosystem's own public registry — the same host the project's package
manager already contacts. Never source, never a path.

`privacy.enrich_dependencies = False` turns it off, and licences then come
from whatever the local manifest or lockfile already records. It stays on in
library mode; an embedded caller that does not want its worker making a
request per dependency sets the flag.

Two things v1 got wrong here:

- **`httpx.Client(timeout=None)`** — a registry that accepts a connection and
  then stalls hangs the scan forever (`L10`).
- **`"License not available"`** written into the licence column on a failed
  lookup, so ATD stores that string as though it were a licence. An unknown
  licence is an absent key.

A dead registry is abandoned after five consecutive failures. There is one
request per dependency; paying a 10-second timeout on each of 400 packages is
an hour of scan time for nothing.

## Declared versus resolved

Both appear in the artifact and are told apart by the specifier: an entry
from a lockfile carries an exact `==` pin, one from a manifest carries the
range that was written. ATD stores it verbatim either way — `==1.2.3` and
`^1.2` mean different things.
