"""Upload semantics: what a status code means and what happens next.

:mod:`test_atd_contract` proves we hit the right URLs with the right bodies.
This proves we react correctly to the answers — which is the half that
decides whether a flaky ATD costs a scan or a retry.
"""

from __future__ import annotations

import copy
import json
import random

import httpx
import pytest

from verinfast2.transport import RETRYABLE, RetryPolicy, UploadConfig, Uploader
from verinfast2.transport.client import NEVER_RETRY, _redact, is_retryable

REPORT = "9a6e8696-f93a-4402-a64e-342ccb37592b"
BASE = "https://atd.example/api"


def uploader_for(handler, **kwargs) -> Uploader:
    """An uploader wired to *handler*, with sleeping stubbed out."""
    kwargs.setdefault("retry", RetryPolicy(attempts=3, backoff=0.0))
    kwargs.setdefault("sleep", lambda _seconds: None)
    return Uploader(
        base_url=BASE,
        report=REPORT,
        config=UploadConfig(uuid=True),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        scan_id="scan-1",
        **kwargs,
    )


class Counter:
    """Always answers *status*, counting how many times it was asked."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(self.status, json={"detail": "x"})


# -- Status semantics -------------------------------------------------------


def test_200_is_success_on_the_first_attempt():
    handler = Counter(200)
    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert result.ok
    assert result.attempts == 1
    assert handler.calls == 1


def test_415_is_never_retried():
    """ClamAV rejecting the payload is a verdict about the bytes. Resending
    them is guaranteed to fail again and costs the scan's time budget."""
    handler = Counter(415)
    result = uploader_for(handler).upload_artifact("findings", "r.git", [])

    assert not result.ok
    assert handler.calls == 1
    assert not result.retryable
    assert "Not retryable" in result.error


def test_502_is_retried_to_the_attempt_limit():
    """The AV scanner being unreachable is exactly the transient case."""
    handler = Counter(502)
    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert not result.ok
    assert handler.calls == 3
    assert result.attempts == 3


def test_404_is_not_retried():
    handler = Counter(404)
    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert handler.calls == 1
    assert "unknown report or scan session" in result.error


def test_422_is_not_retried_and_says_it_is_our_bug():
    handler = Counter(422)
    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert handler.calls == 1
    assert "agent bug" in result.error


def test_415_is_never_retryable():
    """The single most consequential line in the module, asserted directly."""
    assert 415 in NEVER_RETRY
    assert not is_retryable(415)


@pytest.mark.parametrize("status", [500, 501, 502, 503, 504, 505, 507, 599])
def test_every_5xx_is_retryable_not_a_hand_listed_few(status: int):
    """The documented rule is "5xx: yes". A hand-written set meant a 501 or
    507 was given up on after one attempt despite that."""
    assert is_retryable(status)


@pytest.mark.parametrize("status", [200, 400, 404, 409, 415, 422])
def test_no_4xx_except_the_documented_two_is_retryable(status: int):
    assert not is_retryable(status)


def test_408_and_429_are_retryable_despite_being_4xx():
    assert is_retryable(408) and is_retryable(429)
    assert 408 in RETRYABLE and 429 in RETRYABLE


def test_a_501_actually_gets_retried():
    """The behavioural half of the test above."""
    handler = Counter(501)
    uploader_for(handler).upload_artifact("git", "r.git", [])

    assert handler.calls == 3


def test_a_retry_that_eventually_succeeds_reports_success():
    answers = [502, 502, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(answers.pop(0))

    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert result.ok
    assert result.attempts == 3


def test_a_connection_error_is_retryable_and_never_escapes():
    """No status at all: the request may never have arrived."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    result = uploader_for(handler).upload_artifact("git", "r.git", [])

    assert not result.ok
    assert result.status is None
    assert result.retryable
    assert calls["n"] == 3


# -- The credential never reaches a log -------------------------------------


def test_the_report_uuid_is_redacted_from_transport_errors():
    """The UUID is the upload credential, and agent logs get uploaded."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed to connect to {request.url}", request=request)

    result = uploader_for(handler, retry=RetryPolicy(attempts=1)).upload_artifact(
        "git", "r.git", []
    )

    assert REPORT not in result.error
    assert "<report>" in result.error


def test_redact_is_a_no_op_without_a_secret():
    assert _redact("nothing to hide", None) == "nothing to hide"


# -- Disabled mode ----------------------------------------------------------


def test_uploads_disabled_makes_every_call_a_no_op_success():
    """``should_upload: false`` and ``dry: true`` must not fail the scan —
    the artifacts are still produced and returned (`F17`)."""
    handler = Counter(500)
    result = uploader_for(handler, enabled=False).upload_artifact("git", "r.git", [])

    assert result.ok
    assert result.skipped
    assert handler.calls == 0
    assert not result.retryable


def disabled() -> Uploader:
    """A dry-run uploader built the way a caller actually would.

    Deliberately **not** via ``uploader_for``: that fixture pre-sets
    ``scan_id``, which is exactly what hid this whole family of bugs. In a
    real dry run nothing is minted, so nothing sets it.
    """
    return Uploader(base_url=BASE, report=REPORT, enabled=False)


def test_minting_is_a_no_op_success_when_uploads_are_off():
    """`_send` returns ok+skipped, and mint then tried to decode a body that
    was never fetched — so a dry run failed at the first call."""
    result = disabled().mint_scan_session()

    assert result.ok
    assert result.skipped
    assert result.error is None


def test_a_dry_run_uploads_every_artifact_without_a_session():
    """Requiring `scan_id` before checking `enabled` turned every artifact
    in a dry run into a failed upload."""
    uploader = disabled()
    uploader.mint_scan_session()

    for route in ("git", "sizes", "stats", "findings", "dependencies"):
        result = uploader.upload_artifact(route, "r.git", [])
        assert result.ok and result.skipped, f"{route}: {result.error}"


def test_a_dry_run_does_not_need_the_log_file_to_exist():
    result = disabled().upload_log("logs", "/nonexistent/agent.log")

    assert result.ok
    assert result.skipped


def test_a_whole_dry_run_reports_no_failures():
    """The property that matters: `should_upload: false` costs nothing."""
    uploader = disabled()
    results = [
        uploader.mint_scan_session(),
        uploader.upload_artifact("git", "r.git", []),
        uploader.upload_cloud("costs", {}),
        uploader.upload_log("logs", "/nonexistent"),
    ]

    assert all(r.ok and r.skipped for r in results)


# -- Retry policy arithmetic ------------------------------------------------


def test_the_first_attempt_never_waits():
    assert RetryPolicy().wait_for(1) == 0.0


def test_backoff_doubles_and_is_capped():
    policy = RetryPolicy(backoff=1.0, max_backoff=4.0, jitter=0.0)
    rng = random.Random(0)

    assert policy.wait_for(2, rng) == pytest.approx(1.0)
    assert policy.wait_for(3, rng) == pytest.approx(2.0)
    assert policy.wait_for(4, rng) == pytest.approx(4.0)
    assert policy.wait_for(9, rng) == pytest.approx(4.0)


def test_jitter_spreads_waits_around_the_base():
    """A fleet recovering from one ATD outage must not resend in lockstep."""
    policy = RetryPolicy(backoff=10.0, jitter=0.5)
    waits = {policy.wait_for(2, random.Random(seed)) for seed in range(20)}

    assert len(waits) > 1
    assert all(5.0 <= w <= 15.0 for w in waits)


def test_attempts_of_one_disables_retry():
    handler = Counter(503)
    uploader_for(handler, retry=RetryPolicy(attempts=1)).upload_artifact(
        "git", "r.git", []
    )

    assert handler.calls == 1


# -- Client lifecycle -------------------------------------------------------


def test_an_injected_client_is_not_closed_by_the_uploader():
    """Closing a client the caller owns would break their next scan."""
    client = httpx.Client(transport=httpx.MockTransport(Counter(200)))
    uploader = Uploader(base_url=BASE, report=REPORT, client=client)

    uploader.close()

    assert not client.is_closed


def test_base_url_trailing_slash_does_not_double_up():
    """``paths`` always returns a leading slash, so a trailing one on the
    base would produce ``//report/…`` — which some proxies normalise and
    some 404."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json="scan-1")

    uploader = Uploader(
        base_url=BASE + "/",
        report=REPORT,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    uploader.mint_scan_session()

    assert seen == [f"/api/report/{REPORT}/CodeScan"]


# -- Path errors are bugs, not transport failures ---------------------------


def test_an_unknown_route_raises_rather_than_returning_a_failed_result():
    """A typo'd route name is a programming error. Folding it into an
    UploadResult would let it reach production as a "failed upload"."""
    with pytest.raises(ValueError, match="unknown upload route"):
        uploader_for(Counter(200)).upload_cloud("not_a_route", {})


# -- Retry must resend the same bytes ---------------------------------------


def test_a_retried_multipart_upload_resends_the_file_contents(tmp_path):
    """The classic version of this bug passes an open file handle to the HTTP
    client: attempt 1 consumes it, and every retry silently uploads zero
    bytes. The file is read into memory once instead."""
    log = tmp_path / "agent.log"
    log.write_bytes(b"the whole log\n")
    bodies: list[bytes] = []
    answers = [502, 502, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(answers.pop(0))

    result = uploader_for(handler).upload_log("logs", log)

    assert result.ok
    assert len(bodies) == 3
    assert all(b"the whole log" in body for body in bodies)


def test_a_retried_json_upload_resends_the_same_body():
    bodies: list[bytes] = []
    answers = [503, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(answers.pop(0))

    uploader_for(handler).upload_artifact("git", "r.git", [{"commit": "abc"}])

    assert bodies[0] == bodies[1]
    assert b'"commit"' in bodies[0]


# -- Truncation is applied on the way out -----------------------------------


def sent_body(uploader: Uploader, bodies: list) -> dict:
    return json.loads(bodies[-1])


def recorder():
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content)
        return httpx.Response(200, json="ok")

    return handler, bodies


FINDING = {
    "results": [
        {
            "check_id": "python.lang.security.audit.eval-detected",
            "path": "src/engine.py",
            "extra": {
                "lines": "eval(CUSTOMER_PROPRIETARY_BUSINESS_LOGIC)",
                "message": "Detected use of eval().",
            },
        }
    ]
}


def test_findings_are_truncated_at_the_upload_boundary():
    """`privacy.truncate_findings` defaults to on and was enforced nowhere:
    the scanner deliberately returns full source and nothing cut it before
    it went to ATD. A privacy control that is on by default and applied
    never is the worst shape one can take (`S2`)."""
    handler, bodies = recorder()
    uploader = uploader_for(handler)

    uploader.upload_artifact("findings", "r.git", FINDING)
    sent = json.loads(bodies[-1])["results"][0]

    assert sent["extra"]["lines"] == "eval(CUSTOMER_PROPRIETARY_BUSIN"[:30]
    assert len(sent["extra"]["lines"]) == 30


def test_truncation_leaves_the_identifying_fields_alone():
    handler, bodies = recorder()
    uploader_for(handler).upload_artifact("findings", "r.git", FINDING)
    sent = json.loads(bodies[-1])["results"][0]

    assert sent["check_id"] == "python.lang.security.audit.eval-detected"
    assert sent["path"] == "src/engine.py"
    assert sent["extra"]["message"] == "Detected use of eval()."


def test_truncation_does_not_mutate_the_callers_payload():
    """The same object still has to serve the local HTML report."""
    handler, _ = recorder()
    payload = copy.deepcopy(FINDING)
    uploader_for(handler).upload_artifact("findings", "r.git", payload)

    assert payload == FINDING


def test_only_findings_are_truncated():
    """Git messages and dependency summaries are not customer source."""
    handler, bodies = recorder()
    payload = [{"commit": "a", "message": "x" * 100}]
    uploader_for(handler).upload_artifact("git", "r.git", payload)

    assert json.loads(bodies[-1]) == payload


def test_truncation_can_be_turned_off():
    handler, bodies = recorder()
    uploader_for(handler, truncate=False).upload_artifact("findings", "r.git", FINDING)
    sent = json.loads(bodies[-1])["results"][0]

    assert sent["extra"]["lines"] == FINDING["results"][0]["extra"]["lines"]


def test_for_config_carries_the_privacy_settings_across():
    """The constructor that cannot silently lose one."""
    from verinfast2 import ScanConfig

    config = ScanConfig(
        base_url="https://atd.example/api",
        report_id="r",
        should_upload=True,
        privacy={"truncate_findings": True, "truncate_findings_length": 7},
    )
    uploader = Uploader.for_config(config)

    assert uploader.truncate is True
    assert uploader.truncate_length == 7
    assert uploader.enabled is True


def test_for_config_honours_should_upload_false():
    from verinfast2 import ScanConfig

    uploader = Uploader.for_config(ScanConfig(report_id="r", should_upload=False))

    assert uploader.enabled is False


# -- Reading a log file can fail --------------------------------------------


def test_an_unreadable_log_file_is_a_failed_result_not_an_exception(tmp_path):
    """`upload_log` promises never to raise. A permission error on one
    diagnostic file must not abort a scan that otherwise succeeded."""
    log = tmp_path / "agent.log"
    log.write_bytes(b"x")
    log.chmod(0o000)
    try:
        result = uploader_for(Counter(200)).upload_log("logs", log)
    finally:
        log.chmod(0o644)

    if result.ok:  # running as root, where the chmod does not bite
        pytest.skip("cannot make a file unreadable as this user")
    assert "could not read" in result.error


def test_a_directory_passed_as_a_log_file_does_not_raise(tmp_path):
    result = uploader_for(Counter(200)).upload_log("logs", tmp_path)

    assert not result.ok
    assert result.error
