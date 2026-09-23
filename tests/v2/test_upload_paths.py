"""The ATD v3 wire contract.

ATD keeps a literal port of ``verinfast2/transport/paths.py`` in its own
``tests/e2e/upload_paths.py`` and asserts the two agree. The golden case
below is the same one ATD pins, so a drift on either side fails loudly here
instead of silently producing wrong URLs.
"""

import pytest

from verinfast2.transport.paths import (
    DEFAULT_CODE_SEPARATOR,
    UploadConfig,
    routes,
    upload_path,
)

UUID_CFG = UploadConfig(uuid=True)
LEGACY_CFG = UploadConfig(uuid=False)
REPORT = "9a6e8696-f93a-4402-a64e-342ccb37592b"


def test_golden_case_matches_atd():
    """The exact assertion ATD's contract test makes."""
    assert (
        upload_path(UUID_CFG, "scan_id", report=REPORT)
        == f"/report/uuid/{REPORT}/CodeScan"
    )


def test_default_separator_is_codescan():
    """VerinFast/verinfast#814. Servers still pin it for older agents."""
    assert DEFAULT_CODE_SEPARATOR == "/CodeScan"


def test_logs_never_gets_the_uuid_prefix():
    """The one deliberate exception, tested on both sides."""
    assert (
        upload_path(UUID_CFG, "logs", report=REPORT) == f"/report/{REPORT}/agent_logs"
    )


def test_agent_err_does_get_the_uuid_prefix():
    """Asymmetric with agent_logs on purpose."""
    assert (
        upload_path(UUID_CFG, "err_findings", report=REPORT)
        == f"/report/uuid/{REPORT}/agent_err/findings_err"
    )


@pytest.mark.parametrize(
    "route,tail",
    [
        ("git", "git"),
        ("sizes", "sizes"),
        ("stats", "stats"),
        ("findings", "findings"),
        ("dependencies", "dependencies"),
        ("oss", "oss"),
    ],
)
def test_per_repo_routes(route, tail):
    assert (
        upload_path(UUID_CFG, route, report=REPORT, code="scan1", repo="myrepo.git")
        == f"/report/uuid/{REPORT}/CodeScan/scan1/myrepo.git/{tail}"
    )


@pytest.mark.parametrize(
    "route,segment",
    [
        ("costs", "costs"),
        ("instances", "instances"),
        # The route name and the path segment differ here, deliberately.
        ("utilization", "instance_utilization"),
        ("storage", "storage"),
        # Ingest exists on ATD; no agent produces these yet (F8).
        ("user_activity", "user_activity"),
        ("load_balancers", "load_balancers"),
    ],
)
def test_cloud_routes(route, segment):
    assert (
        upload_path(UUID_CFG, route, report=REPORT)
        == f"/report/uuid/{REPORT}/{segment}"
    )


def test_legacy_integer_id_has_no_uuid_segment():
    """ATD keeps the deprecated int-id route family; so must we."""
    assert upload_path(LEGACY_CFG, "git", report=541, code="s1", repo="r") == (
        "/report/541/CodeScan/s1/r/git"
    )


def test_separators_are_overridable():
    cfg = UploadConfig(uuid=True, code_separator="/Legacy", cost_separator="/c")
    assert upload_path(cfg, "scan_id", report=REPORT) == f"/report/uuid/{REPORT}/Legacy"
    assert upload_path(cfg, "costs", report=REPORT) == f"/report/uuid/{REPORT}/c/costs"


def test_prefix_can_be_removed():
    cfg = UploadConfig(prefix=None)
    assert upload_path(cfg, "logs", report=REPORT) == f"{REPORT}/agent_logs"


def test_empty_separators_collapse():
    cfg = UploadConfig(code_separator=None, cost_separator=None)
    assert upload_path(cfg, "scan_id", report=REPORT) == f"/report/{REPORT}"


@pytest.mark.parametrize("route", sorted(routes()))
def test_every_route_builds(route):
    """No route in the table can raise on a fully-populated call."""
    path = upload_path(UUID_CFG, route, report=REPORT, code="s", repo="r")
    assert path.startswith("/report/")


def test_unknown_route_rejected():
    with pytest.raises(ValueError, match="unknown upload route"):
        upload_path(UUID_CFG, "nope", report=REPORT)


@pytest.mark.parametrize(
    "route", ["git", "sizes", "stats", "findings", "dependencies", "oss"]
)
def test_per_repo_routes_require_scan_and_repo(route):
    with pytest.raises(ValueError, match="scan-session id"):
        upload_path(UUID_CFG, route, report=REPORT, repo="r")
    with pytest.raises(ValueError, match="repository name"):
        upload_path(UUID_CFG, route, report=REPORT, code="s")


def test_missing_report_rejected():
    with pytest.raises(ValueError, match="report id or UUID"):
        upload_path(UUID_CFG, "logs", report=None)
