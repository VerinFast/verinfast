# tests/v2/

Tests for `src/verinfast2/`. Kept separate from `tests/` so the v1 suite and
the v2 suite can run and fail independently during the rewrite.

| File | What |
| ---- | ---- |
| `test_upload_paths.py` | the ATD v3 wire contract, including the golden case ATD pins |
| `test_atd_contract.py` | the whole route walk, replayed against a fake ATD |
| `test_uploader.py` | what each status code means and what happens next |
| `test_config_loaders.py` | reading the config ATD serves |
| `test_payloads.py` | truncation — the privacy boundary |
| `test_public_api.py` | the promises that make `verinfast2` importable |
| `test_ruleset.py` | the vendored rules' integrity and licences |
| `atd_fixtures.py` | payload shapes copied from ATD's own contract test |

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

## The contract is tested from both ends

ATD vendors a literal port of our `transport/paths.py` into its
`tests/e2e/upload_paths.py`, and uses it to prove its *server* accepts a
simulated agent run. `atd_fixtures.py` is the same trade in reverse: ATD's
payload shapes, copied here, so `test_atd_contract.py` can prove our *client*
produces that run — same paths, same bodies, same multipart field name, with
an `httpx.MockTransport` standing in for ATD.

Neither side needs the other running. A drift on either side fails a test on
that side. **Both copies are maintained by hand** — if one of these fails,
find out which side moved before changing anything.

## Running

```sh
PYTHONPATH=src python -m pytest tests/v2 -q
```

Offline, no cloud credentials, no package managers — and it must stay that
way.
