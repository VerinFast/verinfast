# dependencies/parsers/

One pure function per manifest format. Signature is always
`(text: str, path: str) -> list[Entry]`.

| File | Formats |
| ---- | ------- |
| `javascript.py` | `package.json`, `package-lock.json` (v1, v2, v3) |
| `python.py` | `requirements*.txt`/`.in`, `Pipfile`, `pyproject.toml`, `poetry.lock` |
| `ruby.py` | `Gemfile`, `Gemfile.lock` |
| `jvm.py` | `pom.xml` |
| `dotnet.py` | `*.csproj` |
| `php.py` | `composer.json` |
| `golang.py` | `go.sum` |
| `container.py` | `Dockerfile`, `docker-compose.yml` |

`__init__.py` holds the dispatch table and the lockfile preference map.

## Why pure

No I/O means a parser is tested from a string literal, which is how the
suite stays offline (`N16`) and how every odd real-world case below got a
test instead of a comment.

## Real-world cases each parser has to get right

- **Go** — `go.sum` has two lines per module and ends with a newline. v1's
  `name, version, hash = line.split(" ")` raised on the trailing blank line,
  so it raised on every file.
- **Maven** — poms are namespaced. v1 searched a bare
  `dependencies/dependency` path, which matches nothing in a real pom.
  Versions may be `${property}` references.
- **NuGet** — a version can be an attribute *or* a child element, and a
  legacy MSBuild `.csproj` is namespaced exactly as a pom is. Both
  selectors use `{*}`; a bare `ItemGroup/PackageReference` path reported
  such a project as having no dependencies at all.
- **npm** — `license` is a string, a `{"type": ...}` dict, or a list of
  either. Lockfile v3 drops the `dependencies` map v1 read.
- **Containers** — the colon in `registry:5000/app` looks exactly like the
  one in `app:1.2`, so the split is anchored on the last slash. `FROM x AS
  builder` names a stage, not part of the image.
- **Ruby** — v1 split `gem install --explain` output on the *last hyphen* to
  separate name from version, mangling `rspec-core`. In a `Gemfile.lock`,
  indentation is the only thing distinguishing a gem from its own
  dependencies.
- **Poetry** — `^0.2.3` pins far more tightly than `^1.2.3`: below 1.0 the
  minor version plays the major's role.
- **Composer** — `php` and `ext-*` are platform requirements, not packages.
