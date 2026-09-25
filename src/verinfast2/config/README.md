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

## Three behaviours the loader gets deliberately right

- **`modules.code.git.start` is honoured.** v1 read it into one attribute and
  looked for it under another, so the configured window was silently ignored
  and every scan walked all of history (`D1`). ATD sends the window anyway,
  "for forward compatibility" — this is that compatibility arriving.
- **`report.uuid` present turns on uuid addressing.** Its presence is the
  signal, exactly as v1 inferred it.
- **`dry: true` and `should_upload: false` each turn uploading off**, and the
  scan still runs and still returns its artifacts.

## Tolerant of ATD, strict about us

An unknown top-level key is ignored, not rejected: a served config follows
another team's deploy cadence, and a new key must not take agents down in the
field. Keys we do recognise are validated strictly — `ScanConfig` sets
`extra="forbid"`.

`from_yaml` is `yaml.safe_load` only. A served config is remote input.

## Current state

Implemented, with `tests/v2/test_config_loaders.py` covering the served
document end to end — including the round trip where a parsed config builds
an `Uploader` that hits the paths ATD's own contract test asserts.
