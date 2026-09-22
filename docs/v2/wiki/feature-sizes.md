---
title: Feature: File Inventory & Sizes
parent: features
artifact: {repo}.sizes.json
route: sizes
tags: v2, feature, code
---

# Feature: File Inventory & Sizes

## What it produces

```
{"files": {".":      {"size", "loc": 0, "ext": null, "directory": true},
           "<path>": {"size", "loc", "ext", "directory": false}, ...},
 "metadata": {"env": <machine>, "real_size": <repo minus .git>,
              "uname": <system>, "branch": <checked-out branch|null>}}
```

The `"."` key is the repo-root entry; ATD v3 lifts its `size` onto
`repository.file_size`. A second artifact, `{repo}.filelist.json`
(`[{"name", "path"}]`), is written as input to
[[Feature: Code Statistics (Modernmetric)]] and is *not* uploaded.

## How v1 does it

`src/verinfast/agent.py::parseRepo`, via `get_raw_size()` and `getloc()`.

- Walks the tree twice: once for the total, once per file.
- `allowfile()` excludes `node_modules`, `.git`, and symlinks.
- LOC is "non-blank lines", counted by reading every file in Python.
- The extension comes from a regex `^[^\.]*\.(.*)` — so `archive.tar.gz`
  yields `tar.gz`, and a dotfile like `.env` yields `env`. Deliberate or not,
  ATD stores it as an opaque string.
- Per-file entries are skipped when `shouldManualFileScan` is false; the
  `filelist` is always built.

## What v2 must keep

- The `"."` root entry and the four `metadata` keys — ATD reads all of them.
- `node_modules` and `.git` exclusion, and never following symlinks.
- Tolerance for unreadable files: `getloc()` swallows every exception and
  returns 0 rather than aborting a scan on one bad file.

## What v2 must change

- **One walk, not three.** Sizes, LOC and the filelist come from a single
  traversal.
- **Exclusions belong in config.** `utils.py` already defines a
  `STD_EXCLUDE_LIST` (build/, dist/, venv/, `__pycache__`, ...) that
  `allowfile()` does not use. Unify them and make the list configurable.
- **Binary files should not be line-counted.** Reading a 400 MB tarball line by
  line to conclude "not many newlines" is the single slowest thing v1 does on a
  large repo.

## Related

[[Feature: Code Statistics (Modernmetric)]] — consumes the filelist
