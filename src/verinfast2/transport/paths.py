"""Every URL the agent posts to.

This module is the ATD v3 wire contract. ATD keeps a literal port of it in
``tests/e2e/upload_paths.py`` and asserts the two agree, so treat any change
here as a change to a published interface: it needs the matching change on
the ATD side and a golden-case test on both.

Kept deliberately small, pure and dependency-free — no HTTP, no config
objects, no I/O. :func:`upload_path` is a function of its arguments and
nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Path segment between the report id and the scan id.
#:
#: ``/CodeScan`` since VerinFast/verinfast#814. Servers still pin this
#: explicitly in the config they serve, because agents released before that
#: fix default to the old product name — so the override below stays
#: load-bearing even though the default is now correct.
DEFAULT_CODE_SEPARATOR: Final = "/CodeScan"
DEFAULT_PREFIX: Final = "/report/"


@dataclass(frozen=True)
class UploadConfig:
    """The per-install parts of a URL.

    Args:
        uuid: whether the report is addressed by UUID. Adds a ``uuid/``
            segment to every route except ``logs`` (see :data:`NO_UUID`).
        prefix: leading segment, ``/report/`` by default.
        code_separator: segment between report id and scan id.
        cost_separator: segment before the cloud routes; usually empty.
    """

    uuid: bool = False
    prefix: str | None = DEFAULT_PREFIX
    code_separator: str | None = DEFAULT_CODE_SEPARATOR
    cost_separator: str | None = None


#: Routes needing a scan id and a repository name.
PER_REPO: Final[frozenset[str]] = frozenset(
    {"git", "sizes", "stats", "findings", "dependencies", "oss"}
)

#: The one route that never takes the ``uuid/`` prefix, even for a
#: uuid-addressed report. Deliberate on both sides; ATD tests for it.
NO_UUID: Final[frozenset[str]] = frozenset({"logs"})


def _routes(
    report: str | int,
    code: str | int | None,
    repo: str | None,
    code_sep: str,
    cost_sep: str,
) -> dict[str, str]:
    per_repo = f"{report}{code_sep}/{code}/{repo}"
    return {
        # Per repository, per scan session.
        "git": f"{per_repo}/git",
        "sizes": f"{per_repo}/sizes",
        "stats": f"{per_repo}/stats",
        "findings": f"{per_repo}/findings",
        "dependencies": f"{per_repo}/dependencies",
        "oss": f"{per_repo}/oss",
        # Per cloud account. The route name and the path segment differ for
        # utilization; keep the route name, it is what ATD's table uses.
        "costs": f"{report}{cost_sep}/costs",
        "instances": f"{report}{cost_sep}/instances",
        "utilization": f"{report}{cost_sep}/instance_utilization",
        "storage": f"{report}{cost_sep}/storage",
        "user_activity": f"{report}{cost_sep}/user_activity",
        "load_balancers": f"{report}{cost_sep}/load_balancers",
        # Session and diagnostics.
        "scan_id": f"{report}{code_sep}",
        "logs": f"{report}/agent_logs",
        "err_stats": f"{report}/agent_err/stats_err",
        "err_findings": f"{report}/agent_err/findings_err",
    }


def routes() -> frozenset[str]:
    """Every route name :func:`upload_path` accepts."""
    return frozenset(_routes("r", "c", "n", "", ""))


def upload_path(
    config: UploadConfig,
    route: str,
    *,
    report: str | int,
    code: str | int | None = None,
    repo: str | None = None,
) -> str:
    """Build the path for one upload.

    Args:
        config: the per-install URL shape.
        route: one of :func:`routes`.
        report: the report UUID, or the deprecated integer id.
        code: the scan-session id, for per-repository routes.
        repo: the repository name, for per-repository routes. Keeps its
            ``.git`` suffix for cloned remotes; it is the directory basename
            for a local scan. Opaque to the server either way.

    Returns:
        A ``baseurl``-relative path, leading slash included.

    Raises:
        ValueError: on an unknown route, a missing report, or a
            per-repository route without ``code``/``repo``.
    """
    if report is None:
        raise ValueError("every upload path needs a report id or UUID")

    code_sep = config.code_separator or ""
    cost_sep = config.cost_separator or ""
    table = _routes(report, code, repo, code_sep, cost_sep)

    if route not in table:
        raise ValueError(
            f"unknown upload route {route!r}; expected one of {sorted(table)}"
        )

    if route in PER_REPO:
        if code is None:
            raise ValueError(f"route {route!r} needs a scan-session id")
        if repo is None:
            raise ValueError(f"route {route!r} needs a repository name")

    path = table[route]
    if config.uuid and route not in NO_UUID:
        path = "uuid/" + path
    if config.prefix is not None:
        path = config.prefix + path
    return path
