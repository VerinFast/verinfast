# tests/v2/

Tests for `src/verinfast2/`. Kept separate from `tests/` so the v1 suite and
the v2 suite can run and fail independently during the rewrite.

| File | What |
| ---- | ---- |
| `test_upload_paths.py` | the ATD v3 wire contract, including the golden case ATD pins |
| `test_public_api.py` | the promises that make `verinfast2` importable |

## These are invariant tests, not coverage

`test_public_api.py` exists to make the five things that made v1
un-importable fail loudly if they come back: argv at import, `input()` in a
constructor, `os.chdir()` as control flow, module-level mutable state, and
hardcoded `~` paths. The first three are checked in a **subprocess with
hostile argv and no stdin**, because checking them in-process proves nothing
once pytest has already imported everything.

`test_upload_paths.py` pins the same golden case ATD v3 asserts from its
side, so a drift between the two repositories fails here rather than
producing plausible-looking wrong URLs.

## Running

```sh
PYTHONPATH=src python -m pytest tests/v2 -q
```

Offline, no cloud credentials, no package managers — and it must stay that
way.
