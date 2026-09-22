---
title: Feature: Git History
parent: features
artifact: {repo}.git.log.json
route: git
tags: v2, feature, code
---

# Feature: Git History

## What it produces

A JSON array, one object per commit:

```
{"message", "author": "Name <email>", "commit": "<sha>", "date": "<RFC2822>",
 "signed": true|false, "merge": true|false,
 "paths": [{"insertions", "deletions", "path"}, ...]}
```

`insertions`/`deletions` are the raw `git log --numstat` strings, so binary
files arrive as `"-"`. ATD v3 expects exactly that.

## How v1 does it

`src/verinfast/agent.py::parseRepo` + `formatGitHash`.

- Checks out the requested branch, falling back to `master`, then to the
  most-recently-committed local branch.
- Runs `git log --since=<start> --numstat --format='%H' <branch> --` through
  `subprocess.run(..., shell=True)` and parses the interleaved output by hand.
- For each hash, shells out **five more times** (`%B`, `%aN <%aE>`, `%H`,
  `%aD`, `git show --format='%G?'`) plus one `git show` to detect merges. A
  thousand-commit repo is six thousand `git` invocations.
- `escapeChars()` backslash-escapes `"`, `{`, `}` in the date; `trimLineBreaks()`
  strips newlines from the message.

## Defects to fix in v2

- **`git init` is run against the scan target.** `parseRepo` calls
  `std_exec(["git", "init"])` before anything else "for Windows support". On a
  `local_repos` scan of a directory that is *not* a repo, this creates a `.git`
  directory in the user's tree. A scanner must not mutate what it scans.
- **The configured start date is ignored.** `config.py`'s
  `handle_config_file` does `g = ["git"]` where it meant `g = c["git"]`, so
  `modules.code.git.start` never reaches `GitModule.start`. Every scan uses the
  built-in default (first of the month, six months back). ATD's own
  `services/code_scan.py` documents this as a known agent quirk and emits its
  preferred window anyway. **v2 must honour the configured window.**
- **Six subprocesses per commit.** One `git log` with a delimited
  `--format` produces the same data in one pass.
- `shell=True` on a command interpolating a config-supplied branch name and
  date is an injection surface.

## What v2 must keep

- The field names and the numstat-string typing (including `"-"`).
- `signed` semantics: v1 treats *anything but* `"N"` as signed. That is
  wrong-ish (`git show --format='%G?'` returns `G`/`B`/`U`/`X`/`Y`/`R`/`E`/`N`,
  and the value is wrapped in quotes by the literal `'%G?'`), but ATD stores it
  as a boolean. Decide in [[Open Questions]] whether to fix the semantics or
  preserve bug-for-bug.
- Full history upload. ATD v3 deliberately removed v1's silent six-month drop.

## Related

[[Feature: File Inventory & Sizes]] · [[Known Defects & Debt]]
