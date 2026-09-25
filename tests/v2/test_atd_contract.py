"""Our half of the ATD v3 agent contract.

ATD's ``tests/e2e/test_agent_contract.py`` proves its *server* accepts a
simulated agent run. This proves our *client* produces that run: the same
route walk, the same paths, the same bodies, the same multipart field name —
with an ``httpx.MockTransport`` standing in for ATD, so it needs no Postgres,
no running service and no network.

Between the two, a drift on either side fails a test on that side.

The paths asserted here are copied from the assertions in ATD's own test, not
recomputed from our own code, which is the only way this catches a change
that is self-consistent on our side and wrong on the wire.
"""

from __future__ import annotations

import json

import httpx
import pytest

import atd_fixtures as fx
from verinfast2.config.loaders import from_yaml
from verinfast2.transport import UploadConfig, Uploader

REPORT = "9a6e8696-f93a-4402-a64e-342ccb37592b"
SCAN_ID = "Xk3mPq7rTyU-vB2nW9zL4cHd"
REPO = "sample-app.git"
BASE = "https://atd.example/api"


class Recorder:
    """A fake ATD that records what it was sent and always says 200."""

    def __init__(self, scan_id: str = SCAN_ID) -> None:
        self.calls: list[httpx.Request] = []
        self.scan_id = scan_id

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=self.scan_id)
        return httpx.Response(200, json={"type": "ok"})

    @property
    def paths(self) -> list[str]:
        return [r.url.path for r in self.calls]

    def body_of(self, path_suffix: str):
        for request in self.calls:
            if request.url.path.endswith(path_suffix):
                return json.loads(request.content)
        raise AssertionError(f"no request ending in {path_suffix!r}")


@pytest.fixture
def atd() -> Recorder:
    return Recorder()


@pytest.fixture
def uploader(atd: Recorder) -> Uploader:
    return Uploader(
        base_url=BASE,
        report=REPORT,
        config=UploadConfig(uuid=True),
        client=httpx.Client(transport=httpx.MockTransport(atd)),
    )


# -- 1. Scan-session mint ---------------------------------------------------


def test_mint_hits_the_path_atd_asserts(uploader: Uploader, atd: Recorder):
    """ATD: ``assert mint_path == f"/report/uuid/{report.uuid}/CodeScan"``."""
    result = uploader.mint_scan_session()

    assert result.ok
    assert atd.paths == [f"/api/report/uuid/{REPORT}/CodeScan"]
    assert uploader.scan_id == SCAN_ID


def test_mint_is_a_GET(uploader: Uploader, atd: Recorder):
    uploader.mint_scan_session()
    assert atd.calls[0].method == "GET"


def test_mint_unwraps_the_json_string_body(atd: Recorder):
    """v1 stripped quotes by hand; decoding JSON does it without guessing."""
    uploader = Uploader(
        base_url=BASE,
        report=REPORT,
        config=UploadConfig(uuid=True),
        client=httpx.Client(transport=httpx.MockTransport(atd)),
    )
    uploader.mint_scan_session()
    assert uploader.scan_id == SCAN_ID
    assert '"' not in uploader.scan_id


def test_an_empty_scan_id_is_a_failure_not_an_empty_string():
    """A blank session id would make every later path structurally valid and
    semantically wrong — better to fail at the mint."""
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=""))
    uploader = Uploader(
        base_url=BASE, report=REPORT, client=httpx.Client(transport=transport)
    )
    result = uploader.mint_scan_session()

    assert not result.ok
    assert "empty scan-session id" in result.error


# -- 2/3. Per-repository artifacts ------------------------------------------


@pytest.mark.parametrize(
    "route,payload",
    [
        ("git", fx.GIT_PAYLOAD),
        ("sizes", fx.SIZES_PAYLOAD),
        ("stats", fx.STATS_PAYLOAD),
        ("findings", fx.FINDINGS_PAYLOAD),
        ("dependencies", fx.DEPENDENCIES_PAYLOAD),
    ],
)
def test_every_repo_artifact_path_and_body(
    uploader: Uploader, atd: Recorder, route: str, payload
):
    """ATD: ``/report/uuid/{uuid}/CodeScan/{scanId}/{repo}/{artifact}``."""
    uploader.mint_scan_session()
    result = uploader.upload_artifact(route, REPO, payload)

    assert result.ok
    assert (
        atd.paths[-1] == f"/api/report/uuid/{REPORT}/CodeScan/{SCAN_ID}/{REPO}/{route}"
    )
    assert atd.calls[-1].method == "POST"
    # Round-trips unchanged: the uploader reshapes nothing.
    assert json.loads(atd.calls[-1].content) == payload


def test_repo_artifacts_are_sent_as_json(uploader: Uploader, atd: Recorder):
    uploader.mint_scan_session()
    uploader.upload_artifact("git", REPO, fx.GIT_PAYLOAD)

    assert atd.calls[-1].headers["content-type"] == "application/json"


def test_a_repo_artifact_without_a_scan_session_is_refused(uploader: Uploader, atd):
    """Not a crash, and not a request with the literal string ``None`` in the
    path — which is what building the URL unguarded would produce."""
    result = uploader.upload_artifact("git", REPO, fx.GIT_PAYLOAD)

    assert not result.ok
    assert "mint_scan_session" in result.error
    assert atd.calls == []


def test_local_repo_names_keep_no_git_suffix(uploader: Uploader, atd: Recorder):
    """ATD's ``test_local_repos_style_repo_name_has_no_forced_git_suffix``: the
    repo segment is opaque, and a local checkout is a bare basename."""
    uploader.mint_scan_session()
    uploader.upload_artifact("sizes", "my-local-checkout", fx.SIZES_PAYLOAD)

    assert atd.paths[-1].endswith("/my-local-checkout/sizes")


# -- 4. Cloud artifacts -----------------------------------------------------


@pytest.mark.parametrize(
    "route,segment,payload",
    [
        ("costs", "costs", fx.COSTS_PAYLOAD),
        ("instances", "instances", fx.INSTANCES_PAYLOAD),
        ("utilization", "instance_utilization", fx.UTILIZATION_PAYLOAD),
        ("storage", "storage", fx.STORAGE_PAYLOAD),
    ],
)
def test_cloud_routes_are_report_scoped(
    uploader: Uploader, atd: Recorder, route: str, segment: str, payload
):
    """No scan id, no repo segment — and ``utilization`` maps to
    ``instance_utilization``, which ATD asserts explicitly."""
    result = uploader.upload_cloud(route, payload)

    assert result.ok
    assert atd.paths[-1] == f"/api/report/uuid/{REPORT}/{segment}"
    assert json.loads(atd.calls[-1].content) == payload


def test_cloud_upload_needs_no_scan_session(uploader: Uploader):
    assert uploader.scan_id is None
    assert uploader.upload_cloud("costs", fx.COSTS_PAYLOAD).ok


# -- 5/6. Logs and error files ----------------------------------------------


def test_agent_logs_never_gets_the_uuid_prefix(uploader: Uploader, atd, tmp_path):
    """The one deliberate asymmetry. ATD asserts
    ``logs_path == f"/report/{report.uuid}/agent_logs"``."""
    log = tmp_path / "log.txt"
    log.write_bytes(b"agent run log\n")

    assert uploader.upload_log("logs", log).ok
    assert atd.paths[-1] == f"/api/report/{REPORT}/agent_logs"
    assert "/uuid/" not in atd.paths[-1]


@pytest.mark.parametrize(
    "route,segment", [("err_stats", "stats_err"), ("err_findings", "findings_err")]
)
def test_agent_err_does_get_the_uuid_prefix(
    uploader: Uploader, atd: Recorder, tmp_path, route: str, segment: str
):
    err = tmp_path / f"{segment}.err"
    err.write_bytes(b"Traceback...\n")

    assert uploader.upload_log(route, err).ok
    assert atd.paths[-1] == f"/api/report/uuid/{REPORT}/agent_err/{segment}"


def test_log_uploads_use_the_logFile_field_name(uploader: Uploader, atd, tmp_path):
    """ATD reads exactly this key out of the multipart body."""
    log = tmp_path / "log.txt"
    log.write_bytes(b"agent run log\n")
    uploader.upload_log("logs", log)

    body = atd.calls[-1].content
    assert b'name="logFile"' in body
    assert b"agent run log" in body
    assert atd.calls[-1].headers["content-type"].startswith("multipart/form-data")


def test_a_missing_log_file_fails_rather_than_silently_succeeding(uploader, atd):
    """A missing file and an unreadable one take the same path now: both are
    "could not read", reported rather than raised."""
    result = uploader.upload_log("logs", "/nonexistent/agent.log")

    assert not result.ok
    assert "could not read" in result.error
    assert atd.calls == []


# -- The legacy int-id family -----------------------------------------------


def test_legacy_id_addressing_has_no_uuid_segment(atd: Recorder):
    """ATD's ``test_full_agent_contract_legacy_id_addressed``."""
    uploader = Uploader(
        base_url=BASE,
        report="12345",
        config=UploadConfig(uuid=False),
        client=httpx.Client(transport=httpx.MockTransport(atd)),
    )
    uploader.mint_scan_session()
    uploader.upload_artifact("git", "legacy-repo", fx.GIT_PAYLOAD)
    uploader.upload_cloud("costs", fx.COSTS_PAYLOAD)

    assert atd.paths == [
        "/api/report/12345/CodeScan",
        f"/api/report/12345/CodeScan/{SCAN_ID}/legacy-repo/git",
        "/api/report/12345/costs",
    ]


# -- The served config the agent fetches first ------------------------------


def test_served_config_round_trips_into_a_working_uploader(atd: Recorder):
    """The whole loop: parse what ATD serves, and the uploader built from it
    hits the paths ATD's own test asserts."""
    config = from_yaml(fx.SERVED_CONFIG_YAML)
    uploader = Uploader(
        base_url=config.base_url,
        report=config.report_id,
        config=config.upload,
        enabled=config.should_upload,
        client=httpx.Client(transport=httpx.MockTransport(atd)),
    )
    uploader.mint_scan_session()

    assert atd.paths == [f"/api/report/uuid/{REPORT}/CodeScan"]


def test_a_full_run_walks_the_contract_table_in_order(
    uploader: Uploader, atd, tmp_path
):
    """One simulated scan, every route, in the order the agent sends them."""
    log = tmp_path / "log.txt"
    log.write_bytes(b"run\n")

    uploader.mint_scan_session()
    for route, payload in (
        ("git", fx.GIT_PAYLOAD),
        ("sizes", fx.SIZES_PAYLOAD),
        ("stats", fx.STATS_PAYLOAD),
        ("findings", fx.FINDINGS_PAYLOAD),
        ("dependencies", fx.DEPENDENCIES_PAYLOAD),
    ):
        assert uploader.upload_artifact(route, REPO, payload).ok
    for route, payload in (
        ("costs", fx.COSTS_PAYLOAD),
        ("instances", fx.INSTANCES_PAYLOAD),
        ("utilization", fx.UTILIZATION_PAYLOAD),
        ("storage", fx.STORAGE_PAYLOAD),
    ):
        assert uploader.upload_cloud(route, payload).ok
    assert uploader.upload_log("logs", log).ok

    prefix = f"/api/report/uuid/{REPORT}"
    assert atd.paths == [
        f"{prefix}/CodeScan",
        f"{prefix}/CodeScan/{SCAN_ID}/{REPO}/git",
        f"{prefix}/CodeScan/{SCAN_ID}/{REPO}/sizes",
        f"{prefix}/CodeScan/{SCAN_ID}/{REPO}/stats",
        f"{prefix}/CodeScan/{SCAN_ID}/{REPO}/findings",
        f"{prefix}/CodeScan/{SCAN_ID}/{REPO}/dependencies",
        f"{prefix}/costs",
        f"{prefix}/instances",
        f"{prefix}/instance_utilization",
        f"{prefix}/storage",
        f"/api/report/{REPORT}/agent_logs",
    ]
