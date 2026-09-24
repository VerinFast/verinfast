"""Getting a remote repository onto disk.

A target from a served config's `repos:` list has a URL and no path. Without
materialisation it reaches every scanner as "no local path" and produces five
quiet skips per repository — a scan that uploads nothing and reports no
failure.

The clone tests use `file://`-style local paths, so the suite stays offline.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from verinfast2 import ScanConfig, Scanner
from verinfast2.core.context import scan_context
from verinfast2.core.materialize import (
    clone_command,
    materialize,
    safe_url,
)
from verinfast2.models import Artifact, Outcome, ScanTarget

HAS_GIT = shutil.which("git") is not None
needs_git = pytest.mark.skipif(not HAS_GIT, reason="git is not installed")


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
def origin(tmp_path: Path) -> Path:
    root = tmp_path / "origin"
    root.mkdir()
    for args in (
        ["init", "-q"],
        ["config", "user.email", "a@b.c"],
        ["config", "user.name", "A"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    (root / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "one"], cwd=root, check=True, capture_output=True
    )
    return root


# -- Credentials never reach a log ------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://x-access-token:ghp_SECRET@github.com/org/repo.git",
            "https://github.com/org/repo.git",
        ),
        (
            "https://user:pass@gitlab.example.com/a/b.git",
            "https://gitlab.example.com/a/b.git",
        ),
        ("https://github.com/org/repo.git", "https://github.com/org/repo.git"),
    ],
)
def test_userinfo_is_stripped_before_a_url_is_logged(url: str, expected: str):
    """A token in the userinfo is an ordinary clone URL, and the agent log
    is itself uploaded (`S5`)."""
    assert safe_url(url) == expected
    assert "SECRET" not in safe_url(url)
    assert "pass" not in safe_url(url)


# -- The command ------------------------------------------------------------


def test_the_url_is_separated_from_the_options():
    """A repository list is input from the served config, so a URL that
    begins with `-` is reachable."""
    command = clone_command("--upload-pack=evil", "/tmp/dest", None)

    assert "--" in command
    assert command.index("--") < command.index("--upload-pack=evil")


def test_a_branch_is_passed_when_given():
    assert "--branch" in clone_command("https://x/y.git", "/tmp/d", "release")


def test_the_clone_is_not_shallow():
    """Git history is one of the five artifacts; `--depth` would silently
    truncate it. The `--since` window bounds the work instead."""
    assert "--depth" not in clone_command("https://x/y.git", "/tmp/d", None)


# -- Materialising ----------------------------------------------------------


def test_a_target_that_already_has_a_path_is_returned_unchanged(tmp_path, ctx_for):
    target = ScanTarget(name="local", path=tmp_path)

    result = materialize(ctx_for(), target)

    assert result.ok
    assert result.target is target


def test_a_target_with_neither_path_nor_url_is_an_error(ctx_for):
    result = materialize(ctx_for(), ScanTarget(name="nothing"))

    assert not result.ok
    assert "neither" in result.error


@needs_git
def test_a_remote_target_is_cloned_into_the_work_directory(origin: Path, ctx_for):
    ctx = ctx_for()
    result = materialize(ctx, ScanTarget(name="app.git", url=str(origin)))

    assert result.ok, result.error
    assert result.target.path is not None
    assert (result.target.path / "app.py").is_file()
    assert ctx.work_dir.resolve() in result.target.path.resolve().parents


@needs_git
def test_the_clone_is_removed_with_the_scan(origin: Path):
    with scan_context(ScanConfig(), log=logging.getLogger("t")) as ctx:
        result = materialize(ctx, ScanTarget(name="app.git", url=str(origin)))
        cloned = result.target.path
        assert cloned.exists()
        work_dir = ctx.work_dir

    assert not work_dir.exists()


@needs_git
def test_materialising_twice_reuses_the_clone(origin: Path, ctx_for):
    ctx = ctx_for()
    first = materialize(ctx, ScanTarget(name="app.git", url=str(origin)))
    second = materialize(ctx, ScanTarget(name="app.git", url=str(origin)))

    assert second.ok, second.error
    assert first.target.path == second.target.path


@needs_git
def test_a_failed_clone_is_an_error_not_an_exception(ctx_for):
    result = materialize(
        ctx_for(), ScanTarget(name="gone", url="/nonexistent/repository.git")
    )

    assert not result.ok
    assert "could not clone" in result.error


@needs_git
def test_a_failed_clones_error_does_not_echo_the_credential(ctx_for, tmp_path):
    secret = tmp_path / "nope"
    url = f"https://tok_SUPERSECRET@example.invalid{secret}"
    result = materialize(ctx_for(), ScanTarget(name="x", url=url))

    assert not result.ok
    assert "SUPERSECRET" not in result.error


# -- Through the orchestrator ----------------------------------------------


@needs_git
def test_a_remote_repository_is_actually_scanned(origin: Path):
    """The finding this module exists for: without it, a served config's
    `repos:` produced five skipped artifacts and scanned nothing."""
    config = ScanConfig(
        targets=[ScanTarget(name="app.git", url=str(origin))],
        privacy={"enrich_dependencies": False},
        write_files=False,
    )
    result = Scanner(config).scan()

    assert result.of(Artifact.SIZES)[0].outcome is Outcome.OK
    assert result.of(Artifact.GIT)[0].outcome is Outcome.OK
    assert result.of(Artifact.GIT)[0].data


@needs_git
def test_a_repository_that_cannot_be_cloned_fails_loudly(tmp_path: Path):
    """One clear failure per artifact, naming the cause — not five copies
    of "no local path" (`F18`)."""
    config = ScanConfig(
        targets=[ScanTarget(name="gone", url="/nonexistent/repo.git")],
        privacy={"enrich_dependencies": False},
        write_files=False,
    )
    result = Scanner(config).scan()

    assert not result.ok
    assert len(result.failed()) == 5
    assert all("could not clone" in a.error for a in result.failed())
