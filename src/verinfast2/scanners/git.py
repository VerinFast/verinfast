"""Git history: commits, authorship and per-file churn.

Ports ``src/verinfast/agent.py::parseRepo + formatGitHash``.

Three things fixed on the way across:

- **Never ``git init`` the target.** v1 ran it unconditionally, which creates
  a ``.git`` directory in a user's tree when the path was not a repository —
  a scanner modifying what it scans (`D3`, `S12`). Here a target with no
  ``.git`` is *skipped, with a reason*, and left untouched.
- **Never check out a branch.** v1 ran ``git checkout`` against the customer's
  working tree, with two fallbacks, which discards nothing only by luck. The
  log is read from whatever ref is asked for; the tree is not moved.
- **One ``git log``, not six per commit.** v1 shelled out five times per hash
  plus a ``git show``, so a 2,000-commit repository meant 12,000 subprocesses
  (`D23`, `N13`). A single ``--format`` with an unlikely delimiter gets the
  same data in one pass.

The wire shape is fixed: numstat values stay **strings**, including ``"-"``
for binary files, because that is what ATD parses.

## The ``signed`` field

v1's ``formatGitHash`` ran ``git show --format='%G?'``, which returns the
value wrapped in the literal quotes from the format string — so the
comparison against a bare ``"N"`` never matched and every commit was reported
as signed. ATD stores the boolean. Here ``%G?`` is read unquoted from the same
single ``git log``, so the value is real: ``G``/``U``/``X``/``Y``/``R`` count
as signed, ``N``/``E`` do not.

This **changes the data** relative to every historical scan: a repository
whose commits were all "signed" will now report most of them unsigned. That
is `Q7`, recorded rather than silently decided — the value here is the
correct one, and whether historical rows get backfilled is someone else's
call.
"""

from __future__ import annotations

import subprocess
from datetime import date
from typing import Any, Final

from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget

#: Field and record separators. ASCII unit/record separators: they cannot
#: occur in a commit message, unlike the newlines and tabs v1 split on.
FIELD_SEP: Final = "\x1f"
RECORD_SEP: Final = "\x1e"

#: ``%G?`` values that mean the signature verified or at least exists.
#: ``N`` is "no signature", ``E`` is "cannot check".
SIGNED_CODES: Final[frozenset[str]] = frozenset({"G", "U", "X", "Y", "R"})

#: The record separator **leads** each commit, because git prints the numstat
#: block *after* the formatted header — so a trailing separator would attach
#: every commit's file list to the next commit.
#:
#: ``%B`` (the raw body) is last and may span lines, so a trailing
#: :data:`FIELD_SEP` closes it: everything after the final field separator in
#: a record is the numstat block, whatever the message contains.
_FORMAT = (
    RECORD_SEP
    + FIELD_SEP.join(["%H", "%aN <%aE>", "%aD", "%G?", "%P", "%B"])
    + FIELD_SEP
)


def is_signed(code: str) -> bool:
    """Whether ``%G?`` *code* counts as a signed commit.

    v1 answered "yes" for everything, because it compared a quote-wrapped
    value against a bare ``"N"`` (`D7`, `Q7`).
    """
    return code.strip() in SIGNED_CODES


def parse_log(raw: str) -> list[dict[str, Any]]:
    """Turn one ``git log --numstat`` run into ATD's commit array.

    Args:
        raw: stdout from :func:`log_command`'s invocation.

    Returns:
        One dict per commit, in log order, each with a ``paths`` list whose
        ``insertions``/``deletions`` stay strings — ``"-"`` included, which
        is what git emits for a binary file and what ATD expects to receive.
    """
    commits: list[dict[str, Any]] = []
    for record in raw.split(RECORD_SEP):
        if not record.strip():
            continue
        # The message is the last field and may span lines, so split off the
        # numstat block from the *right*.
        head, _, numstat = record.rpartition(FIELD_SEP)
        fields = head.split(FIELD_SEP)
        if len(fields) < 6:
            continue
        commit_hash, author, date, signature, parents, message = fields[:6]

        paths: list[dict[str, str]] = []
        for line in numstat.splitlines():
            columns = line.split("\t")
            if len(columns) >= 3 and columns[2]:
                paths.append(
                    {
                        "insertions": columns[0],
                        "deletions": columns[1],
                        "path": columns[2],
                    }
                )

        commits.append(
            {
                "commit": commit_hash,
                "author": author,
                "date": date,
                "message": message.strip(),
                "signed": is_signed(signature),
                # A merge has more than one parent. v1 never populated this
                # from the log at all.
                "merge": len(parents.split()) > 1,
                "paths": paths,
            }
        )
    return commits


def since_argument(start: date) -> str:
    """``--since`` with an explicit midnight, not a bare date.

    git parses a bare ``2024-02-22`` with *approxidate*, which fills in the
    **current time of day**. So ``--since=2024-02-22`` run at 18:00 silently
    means 2024-02-22T18:00, and a commit made that morning is dropped — the
    same scan of the same repository returns different history depending on
    what time it ran.

    v1 passed ATD's bare ``YYYY-MM-DD`` straight through, so every scan has
    had this. Pinning midnight makes the window mean what the config says.
    """
    return f"{start.isoformat()}T00:00:00"


def log_command(since: str | None, ref: str | None) -> list[str]:
    """The one git invocation. No shell, so no quoting to get wrong.

    v1 built this as an f-string and ran it with ``shell=True``, which puts
    a configured date and a branch name from the repository straight into a
    shell command line (`S11`).
    """
    command = ["git", "log", "--numstat", f"--format={_FORMAT}"]
    if since:
        command.append(f"--since={since}")
    if ref:
        command.append(ref)
    # Terminate the revision list so a ref that is also a filename cannot be
    # read as a path.
    command.append("--")
    return command


class GitScanner:
    """Collect one repository's commit history."""

    artifact = Artifact.GIT

    def enabled(self, ctx: ScanContext) -> bool:
        return ctx.config.code.git

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        if target.path is None:
            return self._skip(target, "no local path for this target")
        if target.is_sample:
            # The ATD v3 case. Skipped explicitly rather than synthesised —
            # a sample with no history must not look like a repository with
            # no commits (`F5`, `F18`).
            return self._skip(target, "code sample: no git history to collect")
        if not (target.path / ".git").is_dir():
            # v1 ran `git init` here, creating a .git directory in someone
            # else's tree (`D3`, `S12`).
            return self._skip(target, "not a git repository")

        command = log_command(since_argument(ctx.config.code.git_start), target.branch)
        try:
            completed = subprocess.run(
                command,
                cwd=target.path,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=ctx.config.subprocess_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return self._failed(target, f"could not run git: {exc}")

        if completed.returncode != 0:
            return self._failed(
                target,
                f"git log exited {completed.returncode}: {completed.stderr.strip()}",
            )

        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.OK,
            data=parse_log(completed.stdout),
        )

    def _skip(self, target: ScanTarget, why: str) -> ArtifactResult:
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.SKIPPED,
            error=why,
        )

    def _failed(self, target: ScanTarget, why: str) -> ArtifactResult:
        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.FAILED,
            error=why,
        )
