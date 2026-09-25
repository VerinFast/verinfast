"""The findings scanner.

The Opengrep binary is not a PyPI package, so it may or may not be present.
Everything that does not need it — command construction, exit-code handling,
output parsing, provenance, the failure paths — is tested with a stub engine:
a tiny script that behaves the way the real one does. The one test that needs
the real binary skips cleanly without it, the same way the git and
modernmetric tests do.

That split is deliberate. The failure paths are the ones that matter in the
field and the ones a real engine makes awkward to provoke.
"""

from __future__ import annotations

import json
import logging
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from verinfast2 import ScanConfig
from verinfast2.core.context import scan_context
from verinfast2.models import Artifact, Outcome, ScanTarget
from verinfast2.scanners.findings import PROVENANCE_KEY, RAN, FindingsScanner
from verinfast2.scanners.ruleset import (
    engine_command,
    engine_env,
    load_ruleset,
)

HAS_OPENGREP = shutil.which("opengrep") is not None
needs_opengrep = pytest.mark.skipif(
    not HAS_OPENGREP, reason="the opengrep binary is not installed"
)


@pytest.fixture
def ctx_for():
    made = []

    def build(config: ScanConfig | None = None):
        manager = scan_context(config or ScanConfig(), log=logging.getLogger("test"))
        ctx = manager.__enter__()
        made.append(manager)
        return ctx

    yield build
    for manager in made:
        manager.__exit__(None, None, None)


@pytest.fixture
def target(tmp_path: Path) -> ScanTarget:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("import os\neval(os.environ['X'])\n")
    return ScanTarget(name="repo", path=root)


def stub_engine(tmp_path: Path, *, exit_code: int = 0, output: object = None) -> str:
    """A fake engine: writes *output* to ``--json-output=`` and exits.

    Written as a real executable rather than a monkeypatch of
    ``subprocess.run`` so the argv, the ``cwd`` and the environment are
    exercised end to end — which is where the interesting bugs are.
    """
    script = tmp_path / "fake-engine"
    body = json.dumps(
        {"version": "1.0.0", "errors": [], "results": []} if output is None else output
    )
    script.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        f"payload = {body!r}\n"
        "out = next(\n"
        "    a.split('=', 1)[1] for a in sys.argv if a.startswith('--json-output=')\n"
        ")\n"
        "open(out, 'w').write(payload)\n"
        f"sys.exit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


def silent_engine(tmp_path: Path, *, exit_code: int = 0, stderr: str = "") -> str:
    """An engine that writes no output file."""
    script = tmp_path / "silent-engine"
    script.write_text(
        "#!" + sys.executable + "\n"
        "import sys\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


# -- The command ------------------------------------------------------------


def test_the_command_never_uses_config_auto():
    """Registry rules are licensed for internal, non-competing, non-SaaS use
    only, and fetching them at scan time makes a scan irreproducible."""
    ruleset = load_ruleset()
    argv = engine_command(Path("."), Path("/w/out.json"), ruleset)

    assert "auto" not in argv
    assert "--config" in argv
    assert str(ruleset.path) in argv


def test_the_engine_environment_forces_utf8():
    """Opengrep's bundled interpreter takes its default encoding from the
    locale, and several shipped rules contain typographic punctuation — on a
    container with no LANG it dies while *reading a rule*."""
    env = engine_env({"PATH": "/usr/bin"})

    assert env["LANG"] == "C.UTF-8"
    assert env["LC_ALL"] == "C.UTF-8"
    assert env["PYTHONUTF8"] == "1"


def test_exit_code_one_means_findings_not_failure():
    assert 0 in RAN and 1 in RAN
    assert 2 not in RAN


# -- Success paths ----------------------------------------------------------


def test_a_clean_scan_produces_the_engines_json(tmp_path: Path, target, ctx_for):
    scanner = FindingsScanner(engine=stub_engine(tmp_path))
    result = scanner.run(ctx_for(), target)

    assert result.outcome is Outcome.OK, result.error
    assert result.data["results"] == []
    assert result.data["version"] == "1.0.0"


def test_findings_are_returned_untruncated(tmp_path: Path, target, ctx_for):
    """Cutting the matched source is the upload boundary's job — the local
    HTML report wants the full text, and the same object serves both."""
    source = "eval(os.environ['SOME_VERY_LONG_SECRET_NAME_INDEED'])"
    payload = {
        "version": "1.0.0",
        "errors": [],
        "results": [
            {"check_id": "x", "path": "src/app.py", "extra": {"lines": source}}
        ],
    }
    scanner = FindingsScanner(engine=stub_engine(tmp_path, output=payload))
    result = scanner.run(ctx_for(), target)

    assert result.data["results"][0]["extra"]["lines"] == source


def test_exit_code_one_is_a_success(tmp_path: Path, target, ctx_for):
    payload = {"version": "1.0.0", "errors": [], "results": [{"check_id": "x"}]}
    scanner = FindingsScanner(engine=stub_engine(tmp_path, exit_code=1, output=payload))
    result = scanner.run(ctx_for(), target)

    assert result.outcome is Outcome.OK
    assert len(result.data["results"]) == 1


def test_the_ruleset_provenance_rides_along(tmp_path: Path, target, ctx_for):
    """`S18`: a finding set has to stay explainable months later. ATD's
    ingest models are `extra="allow"`, so the key passes through untouched."""
    scanner = FindingsScanner(engine=stub_engine(tmp_path))
    result = scanner.run(ctx_for(), target)
    provenance = result.data[PROVENANCE_KEY]

    assert provenance["engine"] == "opengrep"
    assert provenance["rule_count"] > 0
    assert provenance["sources"]
    assert all("revision" in source for source in provenance["sources"])
    assert all("license" in source for source in provenance["sources"])


def test_the_scan_target_is_relative_so_paths_do_not_leak(
    tmp_path: Path, target, ctx_for
):
    """The engine puts the path it was given into every finding. An absolute
    one leaks the scanning machine's layout into ATD (`S3`)."""
    recorder = tmp_path / "argv-engine"
    recorder.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "out = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--json-output='))\n"
        "open(out,'w').write(json.dumps({'argv': sys.argv, 'results': [], 'errors': []}))\n"
    )
    recorder.chmod(recorder.stat().st_mode | stat.S_IEXEC)

    result = FindingsScanner(engine=str(recorder)).run(ctx_for(), target)
    argv = result.data["argv"]

    assert argv[-1] == "."
    assert not any(str(target.path) in part for part in argv)


def test_the_engine_runs_in_the_target_directory(tmp_path: Path, target, ctx_for):
    cwd_engine = tmp_path / "cwd-engine"
    cwd_engine.write_text(
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "out = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--json-output='))\n"
        "open(out,'w').write(json.dumps({'cwd': os.getcwd(), 'results': [], 'errors': []}))\n"
    )
    cwd_engine.chmod(cwd_engine.stat().st_mode | stat.S_IEXEC)

    result = FindingsScanner(engine=str(cwd_engine)).run(ctx_for(), target)

    assert Path(result.data["cwd"]).resolve() == target.path.resolve()


def test_the_output_file_is_written_outside_the_scanned_tree(
    tmp_path: Path, target, ctx_for
):
    before = sorted(p.name for p in target.path.rglob("*"))
    FindingsScanner(engine=stub_engine(tmp_path)).run(ctx_for(), target)

    assert sorted(p.name for p in target.path.rglob("*")) == before


# -- Failure paths ----------------------------------------------------------


def test_a_missing_engine_fails_rather_than_skipping(target, ctx_for):
    """Findings were asked for and there are none. That must not look like a
    clean scan (`F18`) — the operator has an install problem."""
    result = FindingsScanner(engine="verinfast-no-such-engine").run(ctx_for(), target)

    assert result.outcome is Outcome.FAILED
    assert "not installed" in result.error


def test_a_nonzero_exit_carries_the_engines_stderr(tmp_path: Path, target, ctx_for):
    engine = silent_engine(tmp_path, exit_code=2, stderr="invalid rule: boom\n")
    result = FindingsScanner(engine=engine).run(ctx_for(), target)

    assert result.outcome is Outcome.FAILED
    assert "exited 2" in result.error
    assert "invalid rule" in result.error


def test_a_success_that_wrote_no_output_is_a_failure(tmp_path: Path, target, ctx_for):
    """Exit 0 with no file means the engine did something unexpected; an
    empty findings list would be a lie."""
    result = FindingsScanner(engine=silent_engine(tmp_path)).run(ctx_for(), target)

    assert result.outcome is Outcome.FAILED
    assert "wrote no output" in result.error


def test_unparseable_output_is_a_failure(tmp_path: Path, target, ctx_for):
    engine = tmp_path / "garbage-engine"
    engine.write_text(
        "#!" + sys.executable + "\n"
        "import sys\n"
        "out = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--json-output='))\n"
        "open(out,'w').write('not json at all')\n"
    )
    engine.chmod(engine.stat().st_mode | stat.S_IEXEC)

    result = FindingsScanner(engine=str(engine)).run(ctx_for(), target)

    assert result.outcome is Outcome.FAILED
    assert "unreadable engine output" in result.error


def test_a_timeout_is_reported_not_raised(tmp_path: Path, target, ctx_for):
    slow = tmp_path / "slow-engine"
    slow.write_text("#!" + sys.executable + "\nimport time\ntime.sleep(30)\n")
    slow.chmod(slow.stat().st_mode | stat.S_IEXEC)
    config = ScanConfig(subprocess_timeout_seconds=0.5)

    result = FindingsScanner(engine=str(slow)).run(ctx_for(config), target)

    assert result.outcome is Outcome.FAILED
    assert "exceeded" in result.error


def test_a_missing_ruleset_says_how_to_fix_it(tmp_path: Path, target, ctx_for):
    scanner = FindingsScanner(
        engine=stub_engine(tmp_path), rules_dir=tmp_path / "no-rules"
    )
    result = scanner.run(ctx_for(), target)

    assert result.outcome is Outcome.FAILED
    assert "sync_rules.py" in result.error


def test_engine_file_errors_are_logged_not_swallowed(
    tmp_path: Path, target, ctx_for, caplog
):
    """A scan where half the tree failed to parse and a scan that genuinely
    found nothing produce the same empty `results` (`F18`)."""
    payload = {
        "version": "1.0.0",
        "errors": [{"path": "src/app.py", "message": "parse error"}],
        "results": [],
    }
    with caplog.at_level(logging.WARNING):
        FindingsScanner(engine=stub_engine(tmp_path, output=payload)).run(
            ctx_for(), target
        )

    assert "1 file-level error" in caplog.text


def test_findings_on_a_target_with_no_path_is_a_skip(tmp_path: Path, ctx_for):
    result = FindingsScanner(engine=stub_engine(tmp_path)).run(
        ctx_for(), ScanTarget(name="remote", url="https://example.invalid/x.git")
    )

    assert result.outcome is Outcome.SKIPPED


def test_disabled_findings_is_reported_by_the_orchestrator(tmp_path: Path, target):
    from verinfast2 import Scanner

    config = ScanConfig(
        targets=[target],
        code={"findings": False},
        privacy={"enrich_dependencies": False},
        write_files=False,
    )
    result = Scanner(config).scan()
    findings = result.of(Artifact.FINDINGS)[0]

    assert findings.outcome is Outcome.SKIPPED
    assert "disabled by configuration" in findings.error


# -- With the real engine ---------------------------------------------------


@needs_opengrep
def test_the_real_engine_runs_the_shipped_ruleset(target, ctx_for):
    """The one test that needs the binary. Everything above proves the
    scanner's own behaviour; this proves the ruleset actually loads."""
    result = FindingsScanner().run(ctx_for(), target)

    assert result.outcome is Outcome.OK, result.error
    assert "results" in result.data
    assert result.data[PROVENANCE_KEY]["rule_count"] > 0


@needs_opengrep
def test_the_real_engine_reports_no_rule_load_errors(target, ctx_for):
    """157 vendored rules, 0 parse errors — the comparison that chose
    Opengrep over Semgrep in the first place."""
    result = FindingsScanner().run(ctx_for(), target)
    errors = [
        error
        for error in result.data.get("errors", [])
        if "rule" in str(error).lower() and "parse" in str(error).lower()
    ]

    assert errors == []


def test_the_scanner_is_wired_into_the_registry():
    from verinfast2.scanners.base import registry

    assert registry()[Artifact.FINDINGS] is FindingsScanner


def test_subprocess_is_how_the_engine_is_invoked():
    """Never an in-process import: a SystemExit from a vendored CLI must not
    reach ATD v3's worker (`L6`, `D18`). Opengrep being a binary makes this
    the only option, and this pins that it stays true."""
    import verinfast2.scanners.findings as module

    source = Path(module.__file__).read_text()

    assert "subprocess.run" in source
    assert "import semgrep" not in source
    assert "opengrep.main" not in source


def test_the_stub_engine_actually_behaves_like_one(tmp_path: Path):
    """The tests above are only worth anything if the stub runs at all."""
    out = tmp_path / "out.json"
    completed = subprocess.run(
        [stub_engine(tmp_path), f"--json-output={out}"], capture_output=True
    )

    assert completed.returncode == 0
    assert json.loads(out.read_text())["results"] == []
