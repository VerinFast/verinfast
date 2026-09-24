"""Getting a remote repository onto disk so scanners can read it.

Every scanner needs ``ScanTarget.path``. A target built from a served
config's ``repos:`` list has a ``url`` and no path, so without this step each
of the five scanners skips it with "no local path" — five quiet skips per
repository, and a scan that uploads nothing while reporting no failure. That
is the `F18` trap with the answer "never ran" hidden behind five copies of
"nothing to do".

**Clones go in the scan's work directory**, which is per-scan and removed on
the way out — never the fixed ``~/.verinfast/temp_repo`` two concurrent scans
would fight over (`S14`, `D5`).

**The clone is not shallow.** `git` history is one of the five artifacts, and
``--depth`` would silently truncate it; the git scanner's ``--since`` window
is what bounds the work. A repository large enough for that to hurt is a real
problem, but a wrong answer is a worse one.

**Credentials are ambient.** The agent runs inside the customer's perimeter,
with their git configuration. Nothing here reads, stores or logs a
credential, and a URL is never echoed into an error — it can carry a token in
its userinfo.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from verinfast2.core.context import ScanContext
from verinfast2.models import ScanTarget


@dataclass(frozen=True)
class Materialized:
    """The outcome of putting one target on disk.

    Attributes:
        target: the target to scan — the original when it already had a
            path, or a copy carrying the clone's path.
        error: why it could not be obtained. ``None`` on success.
    """

    target: ScanTarget | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.target is not None


def safe_url(url: str) -> str:
    """A URL with any userinfo removed, for logs and error messages.

    ``https://x-access-token:ghp_…@github.com/org/repo.git`` is a perfectly
    ordinary clone URL and putting it in an error message writes a live
    credential into the agent log — which is itself uploaded (`S5`).
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<url>"
    if not parts.netloc or "@" not in parts.netloc:
        return url
    host = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def clone_command(url: str, destination: str, branch: str | None) -> list[str]:
    """The argv for one clone. A list, so nothing is shell-quoted.

    ``--`` separates options from the URL: a repository list is input from
    the served config, so a URL beginning with ``-`` is reachable.
    """
    command = ["git", "clone", "--quiet"]
    if branch:
        command += ["--branch", branch]
    command += ["--", url, destination]
    return command


def materialize(ctx: ScanContext, target: ScanTarget) -> Materialized:
    """Ensure *target* has a local path, cloning it if it only has a URL."""
    if target.path is not None:
        return Materialized(target=target)
    if not target.url:
        return Materialized(
            target=None, error="target has neither a local path nor a URL"
        )

    destination = ctx.scratch_for(target.name, "clones") / "repo"
    if destination.exists():
        # A second call for the same target in one scan. The clone is
        # already there; re-cloning would fail on a non-empty directory.
        return Materialized(target=target.model_copy(update={"path": destination}))

    ctx.progress(f"cloning {target.name}", None)
    try:
        completed = subprocess.run(
            clone_command(target.url, str(destination), target.branch),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=ctx.config.clone_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Materialized(
            target=None,
            error=(
                f"cloning {safe_url(target.url)} exceeded "
                f"{ctx.config.clone_timeout_seconds:.0f}s"
            ),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Materialized(
            target=None, error=f"could not run git clone: {type(exc).__name__}: {exc}"
        )

    if completed.returncode != 0:
        detail = _clean(completed.stderr, target.url)
        return Materialized(
            target=None,
            error=f"could not clone {safe_url(target.url)}: {detail}",
        )

    return Materialized(target=target.model_copy(update={"path": destination}))


def _clean(stderr: str, url: str) -> str:
    """git's complaint, with the URL redacted out of it."""
    text = " ".join(stderr.split())[:300]
    return text.replace(url, safe_url(url)) or "git exited non-zero"
