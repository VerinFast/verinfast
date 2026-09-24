"""Amazon Web Services cost and inventory collection.

Ports ``src/verinfast/cloud/aws/``.

**Use ``boto3``, not the ``aws`` CLI.** boto3 is already a dependency, and
the CLI path builds its command as a shell string with a config-supplied
profile name interpolated into it (`D9`, `S9`). Dropping the shell-out also
removes the "is the CLI installed" preflight for AWS.

New collectors: user activity from CloudTrail, load balancers from
ELB/ALB/NLB (`F8`).

## Regions

Both new collectors are regional, so both sweep every region the installed
botocore knows for the service -- read out of its bundled endpoint data, not
fetched, and not the hardcoded list v1 carried (which has been missing
regions since it was written).

A region that refuses is normal, not exceptional: opt-in regions return
``AuthFailure`` for an account that has not enabled them. So a per-region
error is collected and the sweep continues. Only if *every* region failed is
the artifact FAILED -- otherwise a single disabled region would turn a good
inventory into no inventory. The inverse matters just as much: an account
that genuinely has no load balancers returns OK with an empty list, and that
is not the same answer as "every call raised" (`F18`, `F19`).

## boto3 is imported inside the methods

The SDKs are moving behind extras, so importing this module must not require
boto3 -- ``cloud/__init__`` imports all three providers, and a GCP-only scan
should not need the AWS SDK installed to start.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterator

from verinfast2.cloud.base import failed, ok, skipped
from verinfast2.core.context import ScanContext
from verinfast2.models import Artifact, ArtifactResult, CloudAccount

#: CloudTrail keeps 90 days of management events. Asking for more is not an
#: error, it just returns nothing older -- so an unbounded default would look
#: like a 90-day window that silently lies about its span.
LOOKUP_DAYS = 90

#: Ported from v1 unchanged: the four artifacts below are a mechanical port of
#: ``src/verinfast/cloud/aws/{costs,instances,blocks}.py`` and are not in this
#: change. They report SKIPPED with this reason rather than raising, so a scan
#: that asks for them gets a result saying why instead of losing the two that
#: do work (`F19`).
NOT_PORTED = "not ported from v1 yet"


class AwsProvider:
    """Amazon Web Services cost and inventory collection."""

    name = "aws"

    def __init__(
        self, session_factory: Callable[[CloudAccount], Any] | None = None
    ) -> None:
        """
        Args:
            session_factory: builds the boto3 session for an account. The
                seam the tests use: they hand in a fake and the collectors
                never reach the network, which is what lets this file be
                covered by an offline suite at all.
        """
        self._session_factory = session_factory or _default_session

    # -- Availability ---------------------------------------------------

    def available(self, ctx: ScanContext) -> bool:
        """Whether the AWS SDK is importable.

        Deliberately not a credential check: the protocol gives this method
        no account, and credentials are per-account (a profile). An account
        whose credentials are missing reports that per artifact, with the
        error AWS gave, rather than being silently dropped here.
        """
        if self._session_factory is not _default_session:
            return True  # a caller supplied a session; that is the tooling
        # find_spec, not import: this answers "is the SDK installed" without
        # paying to import it, and without leaving boto3 in sys.modules for a
        # scan that then turns out to be GCP-only.
        return importlib.util.find_spec("boto3") is not None

    # -- Ported from v1 (not in this change) -----------------------------

    def costs(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.COSTS, account, NOT_PORTED)

    def instances(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.INSTANCES, account, NOT_PORTED)

    def utilization(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.UTILIZATION, account, NOT_PORTED)

    def storage(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        return skipped(Artifact.STORAGE, account, NOT_PORTED)

    # -- New in v2 -------------------------------------------------------

    def user_activity(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        """Console sign-in and API activity, from CloudTrail.

        ``LookupEvents`` returns management events only, which is what ATD's
        widget is for: who signed in, from where, with MFA or without.
        """
        return self._sweep(
            ctx,
            account,
            Artifact.USER_ACTIVITY,
            service="cloudtrail",
            collect=_events_in_region,
            start=_window(account)[0],
            end=_window(account)[1],
        )

    def load_balancers(self, ctx: ScanContext, account: CloudAccount) -> ArtifactResult:
        """ALB/NLB/Gateway load balancers, plus the classic ones.

        Classic ELBs live behind a different API (``elb``, not ``elbv2``) and
        have no ARN, so their ``id`` is the only stable identifier they have
        -- the name, qualified by region so two same-named balancers in two
        regions do not collapse onto one ATD row under the
        ``(report, provider, account, remote_id)`` key.
        """
        return self._sweep(
            ctx,
            account,
            Artifact.LOAD_BALANCERS,
            service="elbv2",
            collect=_balancers_in_region,
        )

    # -- Internals -------------------------------------------------------

    def _sweep(
        self,
        ctx: ScanContext,
        account: CloudAccount,
        artifact: Artifact,
        *,
        service: str,
        collect: Callable[..., list[dict[str, Any]]],
        **kwargs: Any,
    ) -> ArtifactResult:
        """Run *collect* in every region, tolerating regions that refuse.

        Returns OK with whatever was collected if at least one region
        answered; FAILED only if none did.
        """
        try:
            session = self._session_factory(account)
        except Exception as exc:  # credentials, bad profile name, no SDK
            return failed(artifact, account, f"{type(exc).__name__}: {exc}")

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        answered = 0
        for region in _regions(session, service):
            try:
                rows.extend(collect(session, region, **kwargs))
            except Exception as exc:
                # Normal for opt-in regions; never fatal on its own.
                errors.append(f"{region}: {type(exc).__name__}: {exc}")
                ctx.log.debug("aws %s: %s refused: %s", artifact.value, region, exc)
                continue
            answered += 1

        if answered == 0:
            why = errors[0] if errors else "no regions available for this account"
            return failed(artifact, account, why)
        if errors:
            ctx.log.warning(
                "aws %s: %d of %d regions refused (first: %s)",
                artifact.value,
                len(errors),
                len(errors) + answered,
                errors[0],
            )
        return ok(artifact, account, rows)


# -- Session and regions -------------------------------------------------------


def _default_session(account: CloudAccount) -> Any:
    """A boto3 session for *account*, using its profile when it names one."""
    import boto3

    if account.profile:
        return boto3.session.Session(profile_name=account.profile)
    return boto3.session.Session()


def _regions(session: Any, service: str) -> list[str]:
    """Every region botocore knows offers *service*.

    Read from the SDK's bundled endpoint data -- no call, no network. v1
    carried a hardcoded list instead, which goes stale silently: a region
    added after it was written is simply never scanned.
    """
    regions = list(session.get_available_regions(service))
    return regions or [session.region_name or "us-east-1"]


def _window(account: CloudAccount) -> tuple[datetime, datetime]:
    """The lookup window, as timezone-aware UTC datetimes.

    Dates from config are bare (``YYYY-MM-DD``) and are pinned to midnight
    UTC rather than handed to something that fills in the current time of
    day -- the same trap `D42` records in the git window, where the same
    scan of the same account returned a different span depending on the hour
    it ran.
    """
    end = (
        datetime.combine(account.end, datetime.min.time(), tzinfo=timezone.utc)
        if account.end
        else datetime.now(timezone.utc)
    )
    start = (
        datetime.combine(account.start, datetime.min.time(), tzinfo=timezone.utc)
        if account.start
        else end - timedelta(days=LOOKUP_DAYS)
    )
    return start, end


# -- Collectors ----------------------------------------------------------------


def _paginate(client: Any, operation: str, key: str, **kwargs: Any) -> Iterator[dict]:
    """Yield every item from a paginated call, without holding all pages.

    Uses botocore's paginator when the operation has one and falls back to
    the raw call otherwise, so a fake client in a test only has to implement
    the operation itself.
    """
    if hasattr(client, "get_paginator"):
        try:
            pages = client.get_paginator(operation).paginate(**kwargs)
        except Exception:
            pages = None
        if pages is not None:
            for page in pages:
                yield from page.get(key, [])
            return
    yield from getattr(client, operation)(**kwargs).get(key, [])


def _events_in_region(
    session: Any, region: str, *, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """CloudTrail management events for one region, as ATD rows."""
    client = session.client("cloudtrail", region_name=region)
    rows = []
    for event in _paginate(
        client,
        "lookup_events",
        "Events",
        StartTime=start,
        EndTime=end,
    ):
        rows.append(_event_row(event, region))
    return rows


def _event_row(event: dict, region: str) -> dict[str, Any]:
    """One CloudTrail event in ATD's ``user_activity`` shape.

    The interesting fields are not on the envelope: ``CloudTrailEvent`` is a
    *JSON string* carrying the identity, source IP, user agent and MFA flag.
    A malformed one costs that event's detail, never the sweep.
    """
    try:
        detail = json.loads(event.get("CloudTrailEvent") or "{}")
    except (TypeError, ValueError):
        detail = {}
    identity = detail.get("userIdentity") or {}
    session_ctx = (identity.get("sessionContext") or {}).get("attributes") or {}
    mfa = session_ctx.get("mfaAuthenticated")

    return {
        # ATD upserts on this; CloudTrail's EventId is the only stable id.
        "id": event.get("EventId"),
        "event_time": _isoformat(event.get("EventTime")),
        "event_name": event.get("EventName"),
        "event_source": event.get("EventSource"),
        "event_category": detail.get("eventCategory"),
        "user_name": event.get("Username") or identity.get("userName"),
        "user_arn": identity.get("arn"),
        "user_type": identity.get("type"),
        "source_ip": detail.get("sourceIPAddress"),
        "user_agent": detail.get("userAgent"),
        "region": detail.get("awsRegion") or region,
        # An event with no errorCode succeeded. Absence is the signal here,
        # so `None` would be wrong -- it would read as "unknown".
        "success": "errorCode" not in detail,
        "mfa_used": _as_bool(mfa),
        "details": {
            k: detail[k]
            for k in ("errorCode", "errorMessage", "eventType", "requestID")
            if k in detail
        }
        or None,
    }


def _balancers_in_region(session: Any, region: str) -> list[dict[str, Any]]:
    """Every load balancer in one region -- v2 API first, then classic."""
    rows = [
        _balancer_row(lb, region, session)
        for lb in _paginate(
            session.client("elbv2", region_name=region),
            "describe_load_balancers",
            "LoadBalancers",
        )
    ]
    rows.extend(
        _classic_row(lb, region)
        for lb in _paginate(
            session.client("elb", region_name=region),
            "describe_load_balancers",
            "LoadBalancerDescriptions",
        )
    )
    return rows


def _balancer_row(lb: dict, region: str, session: Any) -> dict[str, Any]:
    """One ALB/NLB/Gateway balancer in ATD's ``load_balancers`` shape."""
    zones = lb.get("AvailabilityZones") or []
    return {
        "id": lb.get("LoadBalancerArn"),
        "name": lb.get("LoadBalancerName"),
        "dns_name": lb.get("DNSName"),
        "lb_type": lb.get("Type"),
        "scheme": lb.get("Scheme"),
        "state": (lb.get("State") or {}).get("Code"),
        "region": region,
        "vpc": lb.get("VpcId"),
        "ip_address_type": lb.get("IpAddressType"),
        # Left unset rather than guessed: a real count means describing every
        # target group and then every group's health, which is two more calls
        # per balancer across every region. ATD's column is nullable and its
        # widget treats absent as unknown, so the honest answer is cheaper
        # and truer than a number that means something else.
        "target_count": None,
        "provider_created_at": _isoformat(lb.get("CreatedTime")),
        "availability_zones": [z.get("ZoneName") for z in zones if z.get("ZoneName")],
        "subnets": [z.get("SubnetId") for z in zones if z.get("SubnetId")],
        "security_groups": lb.get("SecurityGroups") or [],
        "listeners": _listeners(session, region, lb.get("LoadBalancerArn")),
        "attributes": None,
    }


def _listeners(session: Any, region: str, arn: str | None) -> list[dict[str, Any]]:
    """Listener ports and protocols for one balancer.

    One extra call per balancer, unlike the target-health walk above: the
    listener set is what tells you a balancer is serving plain HTTP, which is
    the question the widget exists to answer.
    """
    if not arn:
        return []
    client = session.client("elbv2", region_name=region)
    try:
        listeners = _paginate(
            client, "describe_listeners", "Listeners", LoadBalancerArn=arn
        )
        return [
            {
                "port": item.get("Port"),
                "protocol": item.get("Protocol"),
                "ssl_policy": item.get("SslPolicy"),
            }
            for item in listeners
        ]
    except Exception:
        # A balancer whose listeners we cannot read is still worth reporting.
        return []


def _classic_row(lb: dict, region: str) -> dict[str, Any]:
    """One classic ELB. No ARN, so the id is name-qualified by region."""
    name = lb.get("LoadBalancerName")
    return {
        "id": f"classic/{region}/{name}",
        "name": name,
        "dns_name": lb.get("DNSName"),
        "lb_type": "classic",
        "scheme": lb.get("Scheme"),
        "state": None,
        "region": region,
        "vpc": lb.get("VPCId"),
        "ip_address_type": None,
        "target_count": len(lb.get("Instances") or []),
        "provider_created_at": _isoformat(lb.get("CreatedTime")),
        "availability_zones": list(lb.get("AvailabilityZones") or []),
        "subnets": list(lb.get("Subnets") or []),
        "security_groups": list(lb.get("SecurityGroups") or []),
        "listeners": [
            {
                "port": (item.get("Listener") or {}).get("LoadBalancerPort"),
                "protocol": (item.get("Listener") or {}).get("Protocol"),
            }
            for item in lb.get("ListenerDescriptions") or []
        ],
        "attributes": None,
    }


# -- Small conversions ---------------------------------------------------------


def _isoformat(value: Any) -> str | None:
    """A datetime as ISO-8601, passing through strings and None."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _as_bool(value: Any) -> bool | None:
    """CloudTrail writes its booleans as ``"true"``/``"false"`` strings."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"
