"""The git and sizes scanners, and the orchestration around them.

Offline: the git tests build a real repository in `tmp_path` with `git init`
— on a directory the test owns, which is exactly the thing the scanner must
never do to a target.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from verinfast2 import ScanConfig, Scanner
from verinfast2.core.context import scan_context
from verinfast2.models import Artifact, Outcome, ScanTarget
from verinfast2.scanners.base import registry
from verinfast2.scanners.git import (
    FIELD_SEP,
    RECORD_SEP,
    GitScanner,
    is_signed,
    log_command,
    parse_log,
    since_argument,
)
from verinfast2.scanners.sizes import (
    SizesScanner,
    count_lines,
    extension_of,
    is_binary,
    relative_files,
    walk_files,
)
from verinfast2.scanners.stats import (
    StatsScanner,
    command,
    resolve_tool,
    write_filelist,
)

HAS_GIT = shutil.which("git") is not None
needs_git = pytest.mark.skipif(not HAS_GIT, reason="git is not installed")

HAS_MODERNMETRIC = importlib.util.find_spec("modernmetric") is not None
needs_modernmetric = pytest.mark.skipif(
    not HAS_MODERNMETRIC, reason="modernmetric is not installed"
)


@pytest.fixture
def ctx_for():
    """A ScanContext factory that cleans up after itself."""
    made = []

    def build(config: ScanConfig | None = None):
        manager = scan_context(config or ScanConfig(), log=logging.getLogger("test"))
        ctx = manager.__enter__()
        made.append(manager)
        return ctx

    yield build
    for manager in made:
        manager.__exit__(None, None, None)


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


#: Commit dates are pinned so the ``git_start`` window can be asserted
#: exactly rather than relative to "now".
FIRST_COMMIT_DATE = "2024-02-21T10:00:00+00:00"
SECOND_COMMIT_DATE = "2024-02-22T11:30:00+00:00"


def commit(root: Path, message: str, when: str) -> None:
    """Commit everything staged, at a fixed date."""
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_DATE": when,
    }
    subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=root,
        check=True,
        capture_output=True,
        env=env,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A small real repository: two dated commits, one of them binary."""
    root = tmp_path / "sample-app"
    (root / "src").mkdir(parents=True)
    git("init", "-q", cwd=root)
    git("config", "user.email", "ada@example.com", cwd=root)
    git("config", "user.name", "Ada Lovelace", cwd=root)
    git("config", "commit.gpgsign", "false", cwd=root)

    (root / "src" / "engine.py").write_text("import os\n\n\nprint(os.name)\n")
    git("add", "-A", cwd=root)
    commit(root, "Add analytical engine bindings", FIRST_COMMIT_DATE)

    (root / "assets").mkdir()
    (root / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00binary\x00")
    (root / "src" / "compiler.py").write_text("x = 1\n")
    git("add", "-A", cwd=root)
    commit(root, "Add compiler and logo", SECOND_COMMIT_DATE)
    return root


# -- Pure helpers -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("engine.py", "py"),
        ("archive.tar.gz", "tar.gz"),
        (".gitignore", "gitignore"),
        ("README", ""),
        ("Makefile", ""),
    ],
)
def test_extension_follows_v1s_rule(name: str, expected: str):
    """Everything after the *first* dot. Kept because ATD groups on it and
    two years of rows already use this convention."""
    assert extension_of(name) == expected


def test_a_nul_byte_makes_a_file_binary(tmp_path: Path):
    binary = tmp_path / "logo.png"
    binary.write_bytes(b"\x89PNG\x00\x00")
    text = tmp_path / "code.py"
    text.write_text("x = 1\n")

    assert is_binary(binary)
    assert not is_binary(text)


def test_binary_files_are_not_line_counted(tmp_path: Path):
    """v1 opened everything in text mode and leaned on a bare except, so a
    200 MB asset was decoded byte by byte to produce a meaningless 0
    (`D26`, `N15`)."""
    binary = tmp_path / "logo.png"
    binary.write_bytes(b"\x00" + b"line\n" * 1000)

    assert count_lines(binary) == 0


def test_blank_lines_do_not_count(tmp_path: Path):
    source = tmp_path / "code.py"
    source.write_text("import os\n\n\nprint(1)\n   \n")

    assert count_lines(source) == 2


def test_an_unreadable_file_counts_zero_rather_than_raising(tmp_path: Path):
    assert count_lines(tmp_path / "does-not-exist.py") == 0


# -- The walk ---------------------------------------------------------------


def test_the_walk_never_enters_dot_git(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "objects").write_text("x" * 100)
    (tmp_path / "code.py").write_text("x = 1\n")

    found = {entry.rel for entry in walk_files(tmp_path, [])}

    assert found == {"code.py"}


def test_the_walk_honours_configured_exclusions(tmp_path: Path):
    """v1 hardcoded node_modules and .git, and ignored the venv two
    directories away (`D10`)."""
    (tmp_path / "venv" / "lib").mkdir(parents=True)
    (tmp_path / "venv" / "lib" / "big.py").write_text("x = 1\n")
    (tmp_path / "code.py").write_text("x = 1\n")

    found = {entry.rel for entry in walk_files(tmp_path, ["venv/**", "venv"])}

    assert found == {"code.py"}


def test_symlinks_are_never_followed(tmp_path: Path):
    """Following one can leave the scanned tree entirely; a cycle never
    terminates (`S12`)."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("not ours\n")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "code.py").write_text("x = 1\n")
    try:
        (root / "link").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    found = {entry.rel for entry in walk_files(root, [])}

    assert "outside/secret.txt" not in found
    assert "link/secret.txt" not in found


# -- The sizes artifact -----------------------------------------------------


@needs_git
def test_sizes_produces_atds_shape(repo: Path, ctx_for):
    ctx = ctx_for()
    result = SizesScanner().run(ctx, ScanTarget(name="sample-app", path=repo))

    assert result.outcome is Outcome.OK
    assert set(result.data) == {"files", "metadata"}
    assert set(result.data["metadata"]) == {"env", "real_size", "uname", "branch"}


@needs_git
def test_the_root_entry_is_present_and_shaped_as_atd_expects(repo: Path, ctx_for):
    """ATD lifts this onto `repository.file_size`."""
    result = SizesScanner().run(ctx_for(), ScanTarget(name="s", path=repo))
    root = result.data["files"]["."]

    assert root == {
        "size": root["size"],
        "loc": 0,
        "ext": None,
        "directory": True,
    }
    assert root["size"] > 0


@needs_git
def test_real_size_excludes_the_git_directory(repo: Path, ctx_for):
    result = SizesScanner().run(ctx_for(), ScanTarget(name="s", path=repo))

    assert result.data["metadata"]["real_size"] < result.data["files"]["."]["size"]


@needs_git
def test_file_paths_are_dot_slash_prefixed(repo: Path, ctx_for):
    """ATD merges ReportCodeFile rows by path and rewrites modernmetric's
    paths to `./…`. A bare `src/engine.py` here lands in a different row
    from the same file's stats."""
    result = SizesScanner().run(ctx_for(), ScanTarget(name="s", path=repo))
    paths = set(result.data["files"]) - {"."}

    assert "./src/engine.py" in paths
    assert all(path.startswith("./") for path in paths)


@needs_git
def test_a_binary_file_is_inventoried_with_zero_loc(repo: Path, ctx_for):
    result = SizesScanner().run(ctx_for(), ScanTarget(name="s", path=repo))
    logo = result.data["files"]["./assets/logo.png"]

    assert logo["loc"] == 0
    assert logo["size"] > 0
    assert logo["ext"] == "png"


def test_sizes_on_a_target_with_no_path_is_a_skip_not_a_crash(ctx_for):
    result = SizesScanner().run(
        ctx_for(), ScanTarget(name="remote", url="https://example.invalid/x.git")
    )

    assert result.outcome is Outcome.SKIPPED
    assert result.data is None


# -- Git log parsing --------------------------------------------------------


def raw_record(
    *,
    commit_hash: str = "abc123",
    author: str = "Ada Lovelace <ada@example.com>",
    when: str = "Wed, 21 Feb 2024 10:00:00 +0000",
    signature: str = "N",
    parents: str = "p1",
    message: str = "a message",
    numstat: str = "",
) -> str:
    """One record in the exact layout ``git log --format`` produces.

    Built from the scanner's own separators rather than literal escapes, so
    a change to the format shows up here as a failing assertion rather than
    as a fixture that silently stops resembling git.
    """
    head = FIELD_SEP.join(
        [commit_hash, author, when, signature, parents, message + "\n"]
    )
    return f"{RECORD_SEP}{head}{FIELD_SEP}\n\n{numstat}"


def test_numstat_dashes_stay_strings():
    """git emits `-` for a binary file, and ATD coerces it. Turning it into
    0 here would lose the distinction between "binary" and "no change"."""
    raw = raw_record(numstat="-\t-\tlogo.png\n12\t3\tcode.py\n")

    commits = parse_log(raw)

    assert commits[0]["paths"] == [
        {"insertions": "-", "deletions": "-", "path": "logo.png"},
        {"insertions": "12", "deletions": "3", "path": "code.py"},
    ]


def test_a_multiline_message_containing_a_tab_does_not_break_parsing():
    """v1 split on tabs and newlines, both of which occur in real messages —
    which is why the message is the last field and is closed by a separator
    rather than by a newline."""
    raw = raw_record(
        message="fix:\tindentation\n\nA body paragraph.",
        numstat="1\t0\tcode.py\n",
    )

    commits = parse_log(raw)

    assert len(commits) == 1
    assert "indentation" in commits[0]["message"]
    assert "A body paragraph." in commits[0]["message"]
    assert commits[0]["paths"] == [
        {"insertions": "1", "deletions": "0", "path": "code.py"}
    ]


def test_a_merge_is_detected_from_its_parents():
    assert parse_log(raw_record(parents="p1 p2"))[0]["merge"] is True
    assert parse_log(raw_record(parents="p1"))[0]["merge"] is False
    assert parse_log(raw_record(parents=""))[0]["merge"] is False


def test_an_empty_log_parses_to_no_commits():
    assert parse_log("") == []
    assert parse_log("\n\n") == []


@pytest.mark.parametrize(
    "code,expected", [("G", True), ("U", True), ("N", False), ("E", False)]
)
def test_signed_reads_the_real_gpg_status(code: str, expected: bool):
    """v1 compared a quote-wrapped `%G?` against a bare "N", so every commit
    came back signed (`D7`, `Q7`)."""
    assert is_signed(code) is expected


def test_the_log_command_is_a_list_never_a_shell_string():
    """v1 built this as an f-string and ran it with shell=True, putting a
    configured date and a repository branch name on a command line (`S11`)."""
    command = log_command("2024-01-15", "main")

    assert command[0] == "git"
    assert "--since=2024-01-15" in command
    assert command[-1] == "--"
    assert all(isinstance(part, str) for part in command)


def test_since_pins_midnight_rather_than_passing_a_bare_date():
    """git parses a bare `2024-02-22` with approxidate, which fills in the
    *current time of day*. Passing ATD's bare `YYYY-MM-DD` straight through —
    as v1 did — means the same scan of the same repository returns different
    history depending on what time it ran."""
    assert since_argument(date(2024, 2, 22)) == "2024-02-22T00:00:00"


@needs_git
def test_a_commit_earlier_in_the_start_day_is_still_collected(repo: Path, ctx_for):
    """The behavioural half of the test above. The second commit is at 11:30
    on 2024-02-22; with a bare `--since=2024-02-22` it disappears whenever
    the scan happens to run after 11:30."""
    config = ScanConfig(code={"git_start": date(2024, 2, 22)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))

    assert [c["message"] for c in result.data] == ["Add compiler and logo"]


def test_a_branch_named_like_a_flag_stays_an_argument():
    command = log_command(None, "--upload-pack=evil")

    assert command.count("--") == 1
    assert "--upload-pack=evil" in command


# -- The git scanner --------------------------------------------------------


@needs_git
def test_git_collects_both_commits(repo: Path, ctx_for):
    config = ScanConfig(code={"git_start": date(2024, 1, 1)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))

    assert result.outcome is Outcome.OK
    assert len(result.data) == 2
    assert {"commit", "author", "date", "message", "signed", "merge", "paths"} <= set(
        result.data[0]
    )


@needs_git
def test_git_reports_the_authors_name_and_email(repo: Path, ctx_for):
    config = ScanConfig(code={"git_start": date(2024, 1, 1)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))

    assert result.data[0]["author"] == "Ada Lovelace <ada@example.com>"


@needs_git
def test_git_reports_the_binary_file_as_a_numstat_dash(repo: Path, ctx_for):
    config = ScanConfig(code={"git_start": date(2024, 1, 1)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))
    paths = [p for commit in result.data for p in commit["paths"]]
    logo = next(p for p in paths if p["path"].endswith("logo.png"))

    assert logo["insertions"] == "-"
    assert logo["deletions"] == "-"


def test_git_never_initialises_a_non_repository(tmp_path: Path, ctx_for):
    """The defect this scanner exists to not repeat: v1 ran `git init`
    against whatever it was pointed at (`D3`, `S12`)."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    (plain / "code.py").write_text("x = 1\n")

    result = GitScanner().run(ctx_for(), ScanTarget(name="s", path=plain))

    assert result.outcome is Outcome.SKIPPED
    assert "not a git repository" in result.error
    assert not (plain / ".git").exists()
    assert [p.name for p in plain.iterdir()] == ["code.py"]


def test_a_code_sample_skips_git_rather_than_faking_it(tmp_path: Path, ctx_for):
    """ATD v3's case. "No history" and "a repository with no commits" must
    not produce the same artifact (`F5`, `F18`)."""
    sample = tmp_path / "sample"
    sample.mkdir()

    result = GitScanner().run(
        ctx_for(), ScanTarget(name="s", path=sample, is_sample=True)
    )

    assert result.outcome is Outcome.SKIPPED
    assert "code sample" in result.error


@needs_git
def test_git_start_actually_narrows_the_window(repo: Path, ctx_for):
    """The payoff for D1. The fixture's commits are dated 2024-02-21 and
    2024-02-22, so a start between them must collect exactly one."""
    config = ScanConfig(code={"git_start": date(2024, 2, 22)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))

    assert result.outcome is Outcome.OK
    assert [c["message"] for c in result.data] == ["Add compiler and logo"]


@needs_git
def test_a_start_before_both_commits_collects_both(repo: Path, ctx_for):
    """The control for the test above — without it, a scanner that collected
    nothing at all would pass."""
    config = ScanConfig(code={"git_start": date(2024, 1, 1)})
    result = GitScanner().run(ctx_for(config), ScanTarget(name="s", path=repo))

    assert len(result.data) == 2


# -- Orchestration ----------------------------------------------------------


def test_the_registry_only_claims_scanners_that_exist():
    for artifact, scanner_type in registry().items():
        scanner = scanner_type()
        assert scanner.artifact is artifact
        assert callable(scanner.enabled)
        assert callable(scanner.run)


@needs_git
def test_a_scan_records_a_result_for_every_repo_artifact(repo: Path, tmp_path: Path):
    """An unported scanner is a recorded skip, never a silent absence — a
    clean scan and a scan that never ran must not look alike (`F18`)."""
    config = ScanConfig(
        targets=[ScanTarget(name="sample-app", path=repo)],
        code={"git_start": date(2024, 1, 1)},
        output_dir=tmp_path / "out",
    )
    result = Scanner(config).scan()

    produced = {a.artifact for a in result.artifacts}
    assert produced == {
        Artifact.GIT,
        Artifact.SIZES,
        Artifact.STATS,
        Artifact.FINDINGS,
        Artifact.DEPENDENCIES,
    }
    # Every artifact that did not produce data says why. "Found nothing" and
    # "never ran" must not look alike (`F18`).
    for artifact in result.artifacts:
        if artifact.outcome is Outcome.OK:
            assert artifact.data is not None
        else:
            assert artifact.error, f"{artifact.artifact} gave no reason"


@needs_git
def test_a_scan_writes_each_artifact_when_asked(repo: Path, tmp_path: Path):
    out = tmp_path / "out"
    config = ScanConfig(
        targets=[ScanTarget(name="sample-app", path=repo)],
        code={"git_start": date(2024, 1, 1)},
        output_dir=out,
    )
    result = Scanner(config).scan()

    sizes = result.of(Artifact.SIZES)[0]
    assert sizes.path is not None
    assert sizes.path.exists()
    assert json.loads(sizes.path.read_text())["files"]["."]["directory"] is True


@needs_git
def test_one_scanner_failing_does_not_abort_the_others(repo: Path, monkeypatch):
    """`F19`: five good artifacts must not be lost to one bad one."""

    def explode(self, ctx, target):
        raise RuntimeError("deliberate")

    monkeypatch.setattr(GitScanner, "run", explode)
    config = ScanConfig(
        targets=[ScanTarget(name="sample-app", path=repo)], write_files=False
    )
    result = Scanner(config).scan()

    git_result = result.of(Artifact.GIT)[0]
    assert git_result.outcome is Outcome.FAILED
    assert "deliberate" in git_result.error
    assert result.of(Artifact.SIZES)[0].outcome is Outcome.OK
    assert not result.ok


@needs_git
def test_a_disabled_scanner_is_a_skip_with_a_reason(repo: Path):
    config = ScanConfig(
        targets=[ScanTarget(name="sample-app", path=repo)],
        code={"sizes": False},
        write_files=False,
    )
    result = Scanner(config).scan()

    sizes = result.of(Artifact.SIZES)[0]
    assert sizes.outcome is Outcome.SKIPPED
    assert "disabled by configuration" in sizes.error


@needs_git
def test_every_result_carries_a_duration(repo: Path):
    config = ScanConfig(
        targets=[ScanTarget(name="sample-app", path=repo)], write_files=False
    )
    result = Scanner(config).scan()
    ran = [a for a in result.artifacts if a.outcome is Outcome.OK]

    assert ran
    assert all(a.duration_seconds is not None for a in ran)


@needs_git
def test_scan_path_treats_the_directory_as_a_sample(repo: Path):
    """The ATD v3 entry point: git is skipped rather than synthesised, and
    nothing is written into the scanned tree."""
    before = sorted(p.name for p in repo.iterdir())
    result = Scanner(ScanConfig(embedded=True)).scan_path(str(repo))

    assert result.of(Artifact.GIT)[0].outcome is Outcome.SKIPPED
    assert result.of(Artifact.SIZES)[0].outcome is Outcome.OK
    assert sorted(p.name for p in repo.iterdir()) == before


# -- The stats artifact -----------------------------------------------------


def test_modernmetric_is_invoked_as_a_subprocess_not_imported():
    """v1 did `from modernmetric.__main__ import main` and called it. That
    is a CLI entry point: it may `sys.exit()`, and a SystemExit inside ATD
    v3's worker takes the worker down rather than failing one artifact
    (`D18`, `L6`)."""
    argv = command(
        ["/venv/bin/modernmetric"],
        Path("/w/filelist.json"),
        Path("/w/stats.json"),
        file_timeout=60,
        cache_dir=Path("/w/cache"),
    )

    assert "--file=/w/filelist.json" in argv
    assert "--output=/w/stats.json" in argv


@needs_modernmetric
def test_the_console_script_is_preferred_over_dash_m():
    """Not cosmetic. modernmetric submits `process_file` to a
    multiprocessing Pool, and a function pickles by `__module__` +
    `__qualname__`. Under `python -m modernmetric` that module is
    `"__main__"` — which in a *spawned* child is the `-m` launcher, so the
    child raises AttributeError, the parent times out, and `__main__.py`
    drops the file silently. Every file. Exit code 0, empty `files`.

    `fork` hides it, which is why Linux never saw it; macOS defaults to
    `spawn`, so on the platform most customer laptops run, stats were
    silently empty."""
    launcher = resolve_tool()

    assert launcher is not None
    assert launcher[0].endswith("modernmetric")
    assert "-m" not in launcher


def test_an_uninstalled_tool_resolves_to_nothing():
    assert resolve_tool("verinfast-no-such-tool") is None


def test_the_cache_directory_is_absolute_so_it_escapes_home():
    """modernmetric builds its cache path as `Path(Path.home(), cache_dir,
    cache_db)`, and pathlib discards everything left of an absolute
    component. An absolute directory is the only way to stop it writing a
    SQLite file into the user's home (`L7`, `S15`)."""
    argv = command(
        ["modernmetric"],
        Path("/w/f.json"),
        Path("/w/o.json"),
        file_timeout=60,
        cache_dir=Path("/scan/work/cache"),
    )
    cache_arg = next(a for a in argv if a.startswith("--cache-dir="))
    given = Path(cache_arg.split("=", 1)[1])

    assert given.is_absolute()
    assert Path(Path.home(), given, "db") == Path("/scan/work/cache/db")


def test_the_per_file_timeout_is_pinned_not_left_at_180_seconds():
    """A run that is going to produce nothing should say so in seconds, not
    in hours."""
    argv = command(
        ["modernmetric"],
        Path("/w/f.json"),
        Path("/w/o.json"),
        file_timeout=30,
        cache_dir=Path("/w/c"),
    )

    assert "--file_timeout=30" in argv


def test_the_filelist_carries_repo_relative_paths(tmp_path: Path):
    """modernmetric echoes back exactly the paths it was given, so the
    filelist decides the output's path form."""
    path = tmp_path / "filelist.json"
    write_filelist(path, ["./src/engine.py", "./assets/logo.png"])

    entries = json.loads(path.read_text())

    assert entries == [
        {"name": "engine.py", "path": "./src/engine.py"},
        {"name": "logo.png", "path": "./assets/logo.png"},
    ]


@needs_git
@needs_modernmetric
def test_stats_produces_atds_shape(repo: Path, ctx_for):
    result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=repo))

    assert result.outcome is Outcome.OK, result.error
    assert set(result.data) >= {"files", "overall", "stats"}
    assert set(result.data["stats"]) == {"mean", "median", "min", "max", "sd"}


@needs_git
@needs_modernmetric
def test_stats_paths_need_no_temp_repo_rewrite(repo: Path, ctx_for):
    """The payoff. v1 handed modernmetric absolute paths inside
    `~/.verinfast/temp_repo`, and ATD rewrites `temp_repo/…` to `./…` to
    compensate. Emit the right form and the rewrite is a no-op — and the row
    merges with the same file's sizes entry instead of creating a second."""
    result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=repo))
    paths = set(result.data["files"])

    assert "./src/engine.py" in paths
    assert all(p.startswith("./") for p in paths)
    assert not any("temp_repo" in p for p in paths)


@needs_git
@needs_modernmetric
def test_stats_and_sizes_agree_on_every_path(repo: Path, ctx_for):
    """If these ever diverge, ATD stores two rows per file and every
    per-file join silently halves."""
    ctx = ctx_for()
    target = ScanTarget(name="s", path=repo)
    sizes = SizesScanner().run(ctx, target)
    stats = StatsScanner().run(ctx, target)

    sized = set(sizes.data["files"]) - {"."}
    measured = set(stats.data["files"])

    assert measured <= sized


def test_a_run_that_analysed_nothing_is_a_failure(tmp_path: Path, ctx_for):
    """The safety net. modernmetric drops a file it cannot process and
    carries on, so an empty `files` map is indistinguishable from "analysed
    everything and found nothing" — `F18`, inside a tool we shell out to.

    This is exactly the shape the spawn bug produced: exit 0, empty output.
    """
    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    empty = tmp_path / "empty-tool"
    empty.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "out = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--output='))\n"
        "open(out,'w').write(json.dumps({'files': {}, 'overall': {}, 'stats': {}}))\n"
    )
    empty.chmod(0o755)

    import verinfast2.scanners.stats as stats_module

    original = stats_module.resolve_tool
    stats_module.resolve_tool = lambda name=stats_module.MODULE: [str(empty)]
    try:
        result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=root))
    finally:
        stats_module.resolve_tool = original

    assert result.outcome is Outcome.FAILED
    assert "analysed none of the" in result.error


def test_a_partial_run_is_a_warning_not_a_failure(tmp_path: Path, ctx_for, caplog):
    """One unparseable file should not cost the artifact."""
    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    (root / "b.py").write_text("y = 2\n")
    partial = tmp_path / "partial-tool"
    partial.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "out = next(a.split('=',1)[1] for a in sys.argv if a.startswith('--output='))\n"
        "open(out,'w').write(json.dumps("
        "{'files': {'./a.py': {}}, 'overall': {}, 'stats': {}}))\n"
    )
    partial.chmod(0o755)

    import verinfast2.scanners.stats as stats_module

    original = stats_module.resolve_tool
    stats_module.resolve_tool = lambda name=stats_module.MODULE: [str(partial)]
    try:
        with caplog.at_level(logging.WARNING):
            result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=root))
    finally:
        stats_module.resolve_tool = original

    assert result.outcome is Outcome.OK
    assert "analysed 1 of 2" in caplog.text


@needs_git
def test_stats_never_runs_in_the_scanned_tree(repo: Path, ctx_for):
    """Scratch goes in the scan's work directory. v1 wrote its filelist and
    output next to the customer's code."""
    before = sorted(p.name for p in repo.iterdir())
    StatsScanner().run(ctx_for(), ScanTarget(name="s", path=repo))

    assert sorted(p.name for p in repo.iterdir()) == before


def test_stats_on_an_empty_tree_is_a_skip_with_a_reason(tmp_path: Path, ctx_for):
    """Nothing to measure is not the same as measured nothing (`F18`)."""
    empty = tmp_path / "empty"
    empty.mkdir()

    result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=empty))

    assert result.outcome is Outcome.SKIPPED
    assert "no files" in result.error


def test_a_missing_modernmetric_fails_the_artifact_not_the_scan(
    tmp_path: Path, ctx_for, monkeypatch
):
    """An uninstalled tool must land as a failed artifact carrying the
    reason, not as an exception."""
    import verinfast2.scanners.stats as stats_module

    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(stats_module, "resolve_tool", lambda name=None: None)

    result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=root))

    assert result.outcome is Outcome.FAILED
    assert "not installed" in result.error


def test_a_nonzero_exit_fails_the_artifact_not_the_scan(
    tmp_path: Path, ctx_for, monkeypatch
):
    import verinfast2.scanners.stats as stats_module

    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    broken = tmp_path / "broken-tool"
    broken.write_text(
        "#!" + sys.executable + "\nimport sys\n"
        "sys.stderr.write('boom\\n')\nsys.exit(3)\n"
    )
    broken.chmod(0o755)
    monkeypatch.setattr(stats_module, "resolve_tool", lambda name=None: [str(broken)])

    result = StatsScanner().run(ctx_for(), ScanTarget(name="s", path=root))

    assert result.outcome is Outcome.FAILED
    assert "exited 3" in result.error
    assert "boom" in result.error


# -- The shared file list ---------------------------------------------------


def test_the_tree_is_walked_once_per_target(tmp_path: Path, ctx_for):
    """`sizes` and `stats` both need every file. Walking a large monorepo
    twice is the same waste N12 exists to remove — it just moves the second
    traversal from inside one scanner to between two."""
    root = tmp_path / "code"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    ctx = ctx_for()
    calls = {"n": 0}

    def walk():
        calls["n"] += 1
        return relative_files(root, [])

    assert ctx.files_in("s", walk) == ["./a.py"]
    assert ctx.files_in("s", walk) == ["./a.py"]
    assert calls["n"] == 1


def test_different_targets_get_different_file_lists(tmp_path: Path, ctx_for):
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "a.py").write_text("x = 1\n")
    (second / "b.py").write_text("y = 2\n")
    ctx = ctx_for()

    assert ctx.files_in("one", lambda: relative_files(first, [])) == ["./a.py"]
    assert ctx.files_in("two", lambda: relative_files(second, [])) == ["./b.py"]
