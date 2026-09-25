"""The promises `verinfast2`'s docstring makes, enforced.

These are the five things that made v1 un-importable (`L1`-`L5`). Each one
is a test rather than a comment, so a future change that reintroduces one
fails here instead of surfacing inside ATD v3's worker.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import verinfast2
from verinfast2 import ScanConfig, Scanner, ScanResult
from verinfast2.models import Artifact, ArtifactResult, Outcome
from verinfast2.reporting import run_summary

SRC = str(Path(__file__).resolve().parents[2] / "src")


def _env() -> dict:
    """The current environment with `src` on PYTHONPATH.

    Inherited rather than replaced: clearing HOME or PATH would change what
    is being tested from "the import is well behaved" to "the import copes
    with a stripped environment", and would behave differently on the macOS
    runners.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _run(code: str) -> subprocess.CompletedProcess:
    """Import verinfast2 in a fresh interpreter with hostile argv."""
    return subprocess.run(
        [sys.executable, "-c", code, "--should-not-be-parsed", "--uuid=nope"],
        capture_output=True,
        text=True,
        env=_env(),
        timeout=120,
    )


def test_import_is_silent_and_does_not_read_argv():
    """L1: importing must not print, parse argv, or otherwise react."""
    p = _run("import verinfast2; print('READY')")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "READY"
    assert p.stderr == ""


def test_import_does_not_touch_the_home_directory():
    """L7/S15: no ~/.verinfast, no ~/.verinfast_cache, no preferences file."""
    p = _run(
        "import os, pathlib;"
        "before=set(os.listdir(pathlib.Path.home()));"
        "import verinfast2;"
        "print(sorted(set(os.listdir(pathlib.Path.home())) - before))"
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "[]"


def test_import_does_not_read_stdin():
    """L5: no input() anywhere reachable from import or construction."""
    p = subprocess.run(
        [
            sys.executable,
            "-c",
            "import verinfast2; verinfast2.ScanConfig(); print('OK')",
        ],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env=_env(),
        timeout=120,
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "OK"


def test_public_api_is_explicit():
    assert set(verinfast2.__all__) <= set(dir(verinfast2))
    for name in verinfast2.__all__:
        assert getattr(verinfast2, name) is not None


def test_embedded_mode_is_enforced_by_the_scanner_not_the_caller():
    """L9: a caller cannot forget to disable telemetry or package installs."""
    cfg = ScanConfig(embedded=True)
    cfg.privacy.telemetry = True
    cfg.privacy.upload_logs = True
    cfg.code.allow_package_manager_execution = True

    scanner = Scanner(cfg)

    assert scanner.config.privacy.telemetry is False
    assert scanner.config.privacy.upload_logs is False
    assert scanner.config.code.allow_package_manager_execution is False


def test_non_embedded_config_is_left_alone():
    cfg = ScanConfig(embedded=False)
    cfg.privacy.telemetry = True
    assert Scanner(cfg).config.privacy.telemetry is True


def test_package_manager_execution_is_off_by_default():
    """S7: running the scanned project's package manager is opt-in."""
    assert ScanConfig().code.allow_package_manager_execution is False


def test_truncation_is_on_by_default():
    """S2/Q9: matches what ATD serves, rather than v1's opt-in."""
    privacy = ScanConfig().privacy
    assert privacy.truncate_findings is True
    assert privacy.truncate_findings_length == 30


def test_telemetry_is_off_by_default():
    """S4: the undocumented phone-home becomes explicit and opt-in."""
    assert ScanConfig().privacy.telemetry is False


def test_no_filesystem_default_points_at_home():
    """L7: every path is injectable and none defaults into ~."""
    cfg = ScanConfig()
    assert cfg.work_dir is None
    assert cfg.output_dir is None
    assert cfg.cache_dir is None


def test_git_start_is_honoured_not_dropped():
    """D1/F12: v1 read this from config and then never applied it."""
    from datetime import date

    cfg = ScanConfig(code={"git_start": date(2020, 1, 1)})
    assert cfg.code.git_start == date(2020, 1, 1)


def test_config_rejects_unknown_keys():
    with pytest.raises(Exception):
        ScanConfig(definitely_not_a_field=True)


def test_clean_scan_and_absent_scan_are_distinguishable():
    """F18: an empty result must not look like a failed one."""
    clean = ScanResult()
    clean.artifacts.append(
        ArtifactResult(
            artifact=Artifact.FINDINGS, target="r", outcome=Outcome.OK, data=[]
        )
    )
    broken = ScanResult()
    broken.artifacts.append(
        ArtifactResult(
            artifact=Artifact.FINDINGS, target="r", outcome=Outcome.FAILED, error="boom"
        )
    )
    assert clean.ok and not broken.ok
    assert run_summary(clean)["counts"]["ok"] == 1
    assert run_summary(broken)["errors"][0]["error"] == "boom"


def test_artifact_values_match_upload_routes():
    """The enum doubles as the route table's key; keep them in step."""
    from verinfast2.transport.paths import routes

    known = routes()
    for artifact in Artifact:
        if artifact is Artifact.SYSTEM_INFO:
            continue  # produced locally; ATD has no ingest route for it (Q6)
        assert artifact.value in known, f"{artifact.value} has no upload route"


# -- Home-directory and cleanup guarantees (Sourcery, #817) -----------------


def test_embedded_scan_without_an_output_dir_writes_nothing(tmp_path):
    """S15: the guarantee is enforced, not emergent.

    Before this was explicit, `for_library()` left `write_files` on, so
    nothing stopped an artifact landing somewhere the caller never named.
    """
    cfg = ScanConfig(embedded=True)
    assert cfg.output_dir is None

    scanner = Scanner(cfg)
    assert scanner.config.write_files is False

    from verinfast2.core.context import scan_context

    with scan_context(scanner.config) as ctx:
        assert ctx.artifact_path("repo", "findings") is None


def test_embedded_scan_honours_an_explicit_output_dir(tmp_path):
    """An output directory the caller named is used, wherever it points.

    Refusing paths under ``~`` would break any container whose HOME is the
    working root, so the guarantee is about paths the library *chooses*.
    """
    out = tmp_path / "results"
    cfg = ScanConfig(embedded=True, output_dir=out)

    scanner = Scanner(cfg)
    assert scanner.config.write_files is True

    from verinfast2.core.context import scan_context

    with scan_context(scanner.config) as ctx:
        path = ctx.artifact_path("repo", "findings")
    assert path == out / "repo.findings.json"


def test_work_directory_is_removed_and_is_not_under_home():
    from verinfast2.core.context import scan_context

    with scan_context(ScanConfig(embedded=True)) as ctx:
        work = ctx.work_dir
        assert work.exists()
        assert Path.home() not in work.parents
    assert not work.exists()


def test_a_supplied_work_directory_is_left_alone(tmp_path):
    """We only delete scratch space we created."""
    from verinfast2.core.context import scan_context

    mine = tmp_path / "mine"
    mine.mkdir()
    with scan_context(ScanConfig(embedded=True, work_dir=mine)):
        pass
    assert mine.exists()


def test_cleanup_failure_is_logged_not_swallowed(monkeypatch, caplog):
    """N10: an undeletable scratch tree leaves a clone on someone's disk."""
    import logging
    import shutil

    from verinfast2.core import context as context_mod

    real_rmtree = shutil.rmtree
    leaked = []

    def boom(path, *a, **kw):
        leaked.append(path)
        raise OSError(16, "Device or resource busy")

    monkeypatch.setattr(shutil, "rmtree", boom)

    with caplog.at_level(logging.WARNING, logger="verinfast"):
        with context_mod.scan_context(ScanConfig(embedded=True)):
            pass

    assert any(
        "could not remove scan work directory" in r.getMessage() for r in caplog.records
    ), [r.getMessage() for r in caplog.records]

    for path in leaked:  # the failure was simulated; don't actually leak
        real_rmtree(path, ignore_errors=True)


def test_importing_the_package_does_not_import_an_http_stack():
    """`verinfast2.transport.paths` is copied verbatim into ATD's test suite,
    which is only possible because it depends on nothing. An eager
    ``client`` import in ``transport/__init__`` would put httpx behind
    ``from verinfast2 import ScanConfig`` and behind that vendored port.

    ``Uploader`` resolves lazily instead; this pins that it stays that way.
    """
    p = _run(
        "import sys, verinfast2;"
        "from verinfast2.transport import upload_path;"
        "print('httpx' in sys.modules)"
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "False"


def test_the_uploader_is_still_reachable_from_the_transport_package():
    """The laziness must not cost the import path callers actually use."""
    p = _run("from verinfast2.transport import Uploader;" "print(Uploader.__name__)")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "Uploader"
