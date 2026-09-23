# verinfast2/

The v2 scanning agent. A library first; the CLI is a thin shell over it.

> **Not shipped yet.** `pyproject.toml` builds `src/verinfast/` only. This
> package is importable in tests and in development, and becomes `verinfast`
> at cutover. v1 keeps shipping until then.

## Layout

| Folder | What |
| ------ | ---- |
| `models.py` | Every type that crosses the public boundary. Imports nothing else in the package. |
| `config/` | The `ScanConfig` schema, and loaders for dict / file / URL |
| `core/` | `Scanner` and the per-scan `ScanContext` |
| `scanners/` | One module per code artifact, behind one protocol |
| `cloud/` | AWS / Azure / GCP behind one provider protocol |
| `transport/` | Upload paths, HTTP, retry — **the ATD v3 wire contract** |
| `reporting/` | Local HTML report and the machine-readable run summary |
| `cli/` | Argument parsing, prompts, progress — the only place that prints |

## The rule that shapes everything

Importing `verinfast2` does nothing observable: no `sys.argv`, no prompt, no
home directory, no patched third-party library, no log file. v1 did all five,
which is why it could not be imported.

```python
from verinfast2 import ScanConfig, Scanner
result = Scanner(ScanConfig(embedded=True)).scan_path("/tmp/sample")
```

`embedded=True` additionally refuses telemetry, package-manager execution and
writes to `~`. `Scanner` applies it, so a caller cannot forget to.

## Current state

Implemented: the type model, `transport/paths.py` (with 44 contract tests),
`config/schema.py`, and `core/context.py`. Everything else is an interface
with a `NotImplementedError` body and a docstring naming the v1 source it
ports from and the defects to fix on the way.

## Reading order

`models.py` → `config/schema.py` → `core/scanner.py` → a scanner.

Design rationale lives in the wiki under `docs/v2/`; requirement ids like
`L1` and `S7` in these docstrings resolve there.
