# config/

Building a `ScanConfig`. Nothing here reads the environment on its own.

| File | What |
| ---- | ---- |
| `schema.py` | `ScanConfig` and its nested `CodeConfig` / `PrivacyConfig` |
| `loaders.py` | `from_dict` / `from_yaml` / `from_file` / `from_url` |

## Why this is its own package

v1's `Config.__init__` parsed `sys.argv` unless `"pytest" in sys.argv[0]`.
That string check was the only thing separating library use from CLI use, and
it fails for everything that isn't pytest — including ATD v3. Constructing a
`ScanConfig` here touches nothing ambient; argv lives in `cli/`.

## The YAML keys are ATD's

`loaders.from_dict` reads the document ATD serves at
`GET /api/agent/config/{uuid}/VerinFastConfig.yaml`. The key names are its
interface, not ours — don't rename them.

## Defaults that changed from v1

| Setting | v1 | v2 | Why |
| ------- | -- | -- | --- |
| `privacy.truncate_findings` | off | **on** | matches what ATD serves |
| `privacy.telemetry` | always on, undocumented | **off** | explicit opt-in |
| `code.allow_package_manager_execution` | always on | **off** | runs arbitrary code from the scanned tree |
| `code.git_start` | read, then dropped | **honoured** | v1 bug `D1` |

## Current state

`schema.py` is implemented. Every loader raises `NotImplementedError`; the
mapping is mechanical and `src/verinfast/config.py::handle_config_file` has
the key names.
