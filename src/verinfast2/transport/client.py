"""The HTTP half of the ATD v3 contract.

:mod:`verinfast2.transport.paths` says *where* an artifact goes; this module
says *how* it gets there and what the answer means. The two are deliberately
separate — ATD vendors a literal port of ``paths``, and it can only do that
because ``paths`` has no I/O in it.

**An upload never raises.** Every call returns an :class:`UploadResult`. A
scan that produced five good artifacts and failed to upload one must report
exactly that, not lose four (`F19`, `N10`). The one exception is a
programming error in path construction, which surfaces as ``ValueError`` from
``paths`` before any request is made.

**Retry is driven by ATD's documented status semantics, not by guesswork:**

===== =============================== =========
Code  Meaning                         Retry?
===== =============================== =========
200   accepted                        —
404   unknown report or scan session  no
415   antivirus rejected the payload  **never**
422   payload shape rejected          no
502   antivirus unavailable           yes
5xx   server-side failure             yes
===== =============================== =========

415 is the one that matters. ClamAV rejecting a payload is a verdict about
the bytes, so resending them is guaranteed to fail again — retrying it just
burns the scan's time budget and hammers ATD's AV pipeline. 502 means the
scanner itself was unreachable, which is exactly the transient case retry
exists for.

Retrying at all is only safe because every ingest route is idempotent:
``findings`` and ``dependencies`` delete-and-replace, ``git``/``sizes``/
``stats`` upsert on a natural key, and the cloud routes upsert on
``(report, provider, account, remote_id)``. A duplicate POST costs a
round-trip, never a duplicate row.

**There is no authentication.** The report UUID in the URL is the credential,
so it must never be written to a log or an error message — see
:func:`_redact`.

**Truncation is applied here, on the way out.** The findings scanner returns
the matched source in full, because the local HTML report needs it. Cutting
it is a property of *leaving the machine*, so the uploader does it — see
:meth:`Uploader._shape`. Leaving it to the caller meant
``privacy.truncate_findings`` defaulted to on and was enforced nowhere, which
is the worst shape a privacy control can take (`S2`).
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import httpx

from verinfast2.transport.paths import UploadConfig, upload_path
from verinfast2.transport.payloads import truncate_findings

#: Non-5xx statuses worth sending the same bytes again for.
#:
#: Every 5xx is retryable too — see :func:`is_retryable`, which takes the
#: whole 500–599 range rather than a hand-listed subset. Listing them by hand
#: meant a 501 or 507 was silently given up on despite the documented rule.
RETRYABLE: Final[frozenset[int]] = frozenset({408, 429})

#: The one status that is **never** retried, whatever range it falls in.
#: ClamAV rejecting a payload is a verdict about the bytes.
NEVER_RETRY: Final[frozenset[int]] = frozenset({415})


def is_retryable(status: int | None) -> bool:
    """Whether *status* is worth another attempt.

    ``None`` means no response arrived at all — connection refused, DNS
    failure, timeout — so the request may never have reached ATD.
    """
    if status is None:
        return True
    if status in NEVER_RETRY:
        return False
    return status in RETRYABLE or 500 <= status <= 599


#: Field name for every multipart upload. ATD reads exactly this key.
LOG_FIELD: Final = "logFile"

_JSON_HEADERS: Final = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _redact(text: str, secret: str | int | None) -> str:
    """Remove the report id from a string bound for a log.

    The UUID is the upload credential (`S5`). An exception message that
    quotes the failing URL would otherwise put it in every log file the
    agent uploads.
    """
    if secret is None:
        return text
    return text.replace(str(secret), "<report>")


@dataclass(frozen=True)
class UploadResult:
    """What happened to one upload.

    Attributes:
        ok: the server accepted it.
        route: the logical route name, not the URL.
        status: HTTP status, or None if no response was ever received.
        attempts: how many requests were actually sent.
        error: why it failed, with the report id redacted.
        body: the decoded response body, when there was one.
        skipped: no request was made — uploads are off, or dry run.
    """

    ok: bool
    route: str
    status: int | None = None
    attempts: int = 0
    error: str | None = None
    body: Any = None
    skipped: bool = False

    @property
    def retryable(self) -> bool:
        """Whether sending the same bytes again could plausibly work.

        A result with no status at all (connection refused, DNS failure,
        timeout) is retryable; the request may never have reached ATD.
        """
        if self.ok or self.skipped:
            return False
        return is_retryable(self.status)


@dataclass
class RetryPolicy:
    """How hard to try. Bounded, jittered, and off by default in tests.

    Attributes:
        attempts: total requests for one upload, not retries after the
            first. ``1`` disables retry.
        backoff: seconds before the second attempt; doubles each time.
        max_backoff: ceiling for one wait.
        jitter: fraction of the computed wait to randomise by, so a fleet of
            agents recovering from the same ATD outage does not resend in
            lockstep.
    """

    attempts: int = 3
    backoff: float = 1.0
    max_backoff: float = 30.0
    jitter: float = 0.25

    def wait_for(self, attempt: int, rng: random.Random | None = None) -> float:
        """Seconds to sleep before *attempt* (1-based; attempt 1 never waits)."""
        if attempt <= 1:
            return 0.0
        base = min(self.backoff * (2 ** (attempt - 2)), self.max_backoff)
        spread = base * self.jitter
        return (rng or random).uniform(max(0.0, base - spread), base + spread)


@dataclass
class Uploader:
    """Send one scan's artifacts to ATD v3.

    The client is injectable so tests never touch a socket:

        >>> transport = httpx.MockTransport(lambda r: httpx.Response(200))
        >>> up = Uploader(
        ...     base_url="https://atd.example/api",
        ...     report="9a6e8696",
        ...     config=UploadConfig(uuid=True),
        ...     client=httpx.Client(transport=transport),
        ... )
        >>> up.mint_scan_session().ok
        True

    Args:
        base_url: ATD's API root, mount path included. Trailing slash
            optional.
        report: the report UUID, or the deprecated integer id.
        config: the URL shape ATD served in ``server:``.
        client: an ``httpx.Client``; one is built lazily if omitted.
        enabled: ``False`` makes every call a no-op success. This is how
            ``should_upload: false`` and ``dry: true`` are honoured — the
            scan still runs and still returns its artifacts (`F17`).
        retry: see :class:`RetryPolicy`.
        timeout: per-request ceiling, seconds.
        sleep: injectable for tests; defaults to :func:`time.sleep`.
        truncate: cut matched source out of the findings payload before
            sending. Defaults to on, matching ``PrivacyConfig`` and what ATD
            serves. Build one with :meth:`for_config`.
        truncate_length: characters of each string to keep.
    """

    base_url: str
    report: str | int
    config: UploadConfig = field(default_factory=UploadConfig)
    client: httpx.Client | None = None
    enabled: bool = True
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: float = 120.0
    sleep: Any = time.sleep
    truncate: bool = True
    truncate_length: int = 30
    #: Minted by :meth:`mint_scan_session`; required by per-repo routes.
    scan_id: str | None = None

    _owns_client: bool = field(default=False, init=False, repr=False)

    # -- Lifecycle ------------------------------------------------------

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    @classmethod
    def for_config(cls, config: Any, **overrides: Any) -> Uploader:
        """Build an uploader from a :class:`~verinfast2.config.schema.ScanConfig`.

        The only constructor that cannot silently lose a privacy setting:
        ``should_upload`` and both truncation settings come across together.
        Prefer it over calling ``Uploader(...)`` by hand.
        """
        kwargs: dict[str, Any] = {
            "base_url": config.base_url or "",
            "report": config.report_id,
            "config": config.upload,
            "enabled": config.should_upload,
            "truncate": config.privacy.truncate_findings,
            "truncate_length": config.privacy.truncate_findings_length,
        }
        kwargs.update(overrides)
        return cls(**kwargs)

    def _shape(self, route: str, payload: Any) -> Any:
        """Apply the privacy policy that belongs to leaving the machine.

        Only ``findings`` carries customer source. Everything else goes as
        the scanner produced it.
        """
        if route == "findings" and self.truncate:
            return truncate_findings(
                payload, enabled=True, max_length=self.truncate_length
            )
        return payload

    def _http(self) -> httpx.Client:
        if self.client is None:
            self.client = httpx.Client(timeout=self.timeout, follow_redirects=False)
            self._owns_client = True
        return self.client

    def close(self) -> None:
        """Close the client, but only one this uploader created itself."""
        if self._owns_client and self.client is not None:
            self.client.close()
            self.client = None
            self._owns_client = False

    def __enter__(self) -> Uploader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- The contract ---------------------------------------------------

    def mint_scan_session(self) -> UploadResult:
        """``GET {prefix}{report}{code_separator}`` — start a scan run.

        ATD mints a fresh ``CodeScanRun`` per call and returns its id as a
        JSON string. v1 stripped surrounding quotes by hand; decoding the
        JSON does the same thing without guessing.

        On success :attr:`scan_id` is set, which is what every per-repository
        route needs.
        """
        result = self._send("scan_id", method="GET")
        if result.skipped:
            # Uploads are off. There is no session to mint and no body to
            # decode; the documented no-op success has to survive intact.
            return result
        if result.ok:
            self.scan_id = _decode_scan_id(result.body)
            if not self.scan_id:
                return UploadResult(
                    ok=False,
                    route="scan_id",
                    status=result.status,
                    attempts=result.attempts,
                    error="server returned an empty scan-session id",
                )
        return result

    def upload_artifact(self, route: str, repo: str, payload: Any) -> UploadResult:
        """POST one per-repository artifact as JSON.

        Args:
            route: ``git``, ``sizes``, ``stats``, ``findings`` or
                ``dependencies``.
            repo: the repository name. Keeps its ``.git`` suffix for a
                cloned remote; the directory basename for a local scan.
                Opaque to ATD either way.
            payload: already in ATD's shape. This module does not reshape
                anything — see :mod:`verinfast2.transport.payloads`.
        """
        if not self.enabled:
            # Nothing was minted because nothing is being sent. Checking the
            # session first turned every dry run into a failed upload.
            return UploadResult(ok=True, route=route, skipped=True)
        if self.scan_id is None:
            return UploadResult(
                ok=False,
                route=route,
                error="no scan session; call mint_scan_session() first",
            )
        return self._send(
            route, method="POST", json_body=self._shape(route, payload), repo=repo
        )

    def upload_cloud(self, route: str, payload: Any) -> UploadResult:
        """POST one cloud artifact. Report-scoped: no scan id, no repo."""
        return self._send(route, method="POST", json_body=payload)

    def upload_log(self, route: str, path: str | Path) -> UploadResult:
        """POST a diagnostic file as multipart under ``logFile``.

        Args:
            route: ``logs``, ``err_stats`` or ``err_findings``. Note that
                ``logs`` alone never takes the ``uuid/`` prefix — a
                deliberate asymmetry both repositories test for.
            path: the file to send. A missing file is a failure, not a
                silent success; v1 returned ``False`` here and callers
                ignored it.
        """
        if not self.enabled:
            return UploadResult(ok=True, route=route, skipped=True)
        file_path = Path(path)
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            # `upload_log` promises never to raise. A permission error or a
            # log rotated out from under us must not abort a scan that
            # otherwise succeeded.
            return UploadResult(
                ok=False,
                route=route,
                error=_redact(f"could not read {file_path.name}: {exc}", self.report),
            )
        files = {LOG_FIELD: (file_path.name, data, "application/octet-stream")}
        return self._send(route, method="POST", files=files)

    # -- Internals ------------------------------------------------------

    def _send(
        self,
        route: str,
        *,
        method: str,
        json_body: Any = None,
        files: dict[str, Any] | None = None,
        repo: str | None = None,
    ) -> UploadResult:
        """One request, with bounded retry. Never raises."""
        if not self.enabled:
            return UploadResult(ok=True, route=route, skipped=True)

        # Path errors are bugs in the caller, not transport failures, so they
        # are raised rather than folded into an UploadResult.
        path = upload_path(
            self.config, route, report=self.report, code=self.scan_id, repo=repo
        )
        url = self.base_url + path

        content: bytes | None = None
        headers: dict[str, str] | None = None
        if json_body is not None:
            content = json.dumps(json_body).encode("utf-8")
            headers = dict(_JSON_HEADERS)

        last = UploadResult(ok=False, route=route, error="no attempt was made")
        for attempt in range(1, max(1, self.retry.attempts) + 1):
            if attempt > 1:
                self.sleep(self.retry.wait_for(attempt))
            last = self._attempt(route, method, url, content, headers, files, attempt)
            if last.ok or not last.retryable:
                return last
        return last

    def _attempt(
        self,
        route: str,
        method: str,
        url: str,
        content: bytes | None,
        headers: dict[str, str] | None,
        files: dict[str, Any] | None,
        attempt: int,
    ) -> UploadResult:
        try:
            response = self._http().request(
                method,
                url,
                content=content,
                headers=headers,
                files=files,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            # No status at all: the request may never have arrived, so this
            # stays retryable. The message can contain the URL, hence redact.
            return UploadResult(
                ok=False,
                route=route,
                attempts=attempt,
                error=_redact(f"{type(exc).__name__}: {exc}", self.report),
            )

        if response.status_code == 200:
            return UploadResult(
                ok=True,
                route=route,
                status=200,
                attempts=attempt,
                body=_decode(response),
            )
        return UploadResult(
            ok=False,
            route=route,
            status=response.status_code,
            attempts=attempt,
            error=_explain(response.status_code, route),
        )


def _decode(response: httpx.Response) -> Any:
    """The body as JSON when it parses, as text when it does not."""
    try:
        return response.json()
    except ValueError:
        return response.text


def _decode_scan_id(body: Any) -> str | None:
    """ATD returns a JSON string; tolerate a bare one from an older build."""
    if isinstance(body, str):
        return body.strip().strip('"') or None
    if isinstance(body, dict):
        for key in ("uuid", "scan_id", "id"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _explain(status: int, route: str) -> str:
    """A message that says what to do, not just what happened."""
    if status == 404:
        return (
            f"{route}: unknown report or scan session (404). ATD also returns "
            "404 instead of 403, so this can mean the report is not visible "
            "to this credential."
        )
    if status == 415:
        return (
            f"{route}: rejected by antivirus scan (415). Not retryable — the "
            "payload itself is the problem."
        )
    if status == 422:
        return (
            f"{route}: payload shape rejected (422). This is an agent bug; "
            "ATD does not use 422 for lookup misses."
        )
    if status == 502:
        return f"{route}: antivirus unavailable (502). Retryable."
    return f"{route}: server returned {status}."
