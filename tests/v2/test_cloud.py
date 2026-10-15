"""Cloud collection: the provider registry, AWS's two new artifacts, and the
orchestrator that runs them.

Offline by construction. Every test hands the provider a fake boto3 session,
so nothing here can reach AWS even if the socket guard is not installed --
which matters, because a collector that needs the network in a test is one
that will make a customer's scan phone out.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from verinfast2.cloud.aws import AwsProvider, _window
from verinfast2.cloud.base import ok, provider_for
from verinfast2.config.schema import ScanConfig
from verinfast2.core.context import scan_context
from verinfast2.core.scanner import Scanner
from verinfast2.models import CLOUD_ARTIFACTS, Artifact, CloudAccount, Outcome

# -- Fakes ---------------------------------------------------------------------


class FakeClient:
    """A boto3 client with only the operations a test needs."""

    def __init__(self, **operations):
        self._operations = operations
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name):
        if name not in self._operations:
            raise AttributeError(name)

        def call(**kwargs):
            self.calls.append((name, kwargs))
            value = self._operations[name]
            return value(**kwargs) if callable(value) else value

        return call


class FakeSession:
    """Hands out fake clients and a fixed region list."""

    def __init__(self, clients, regions=("us-east-1",)):
        self._clients = clients
        self._regions = list(regions)
        self.region_name = self._regions[0] if self._regions else None

    def get_available_regions(self, service):
        return list(self._regions)

    def client(self, name, region_name=None):
        entry = self._clients[name]
        return entry(region_name) if callable(entry) else entry


def aws_with(clients, regions=("us-east-1",)) -> AwsProvider:
    return AwsProvider(session_factory=lambda account: FakeSession(clients, regions))


ACCOUNT = CloudAccount(provider="aws", account="123456789012")


@pytest.fixture
def ctx():
    with scan_context(ScanConfig(write_files=False)) as context:
        yield context


def trail_event(**overrides):
    """A CloudTrail LookupEvents entry, envelope plus embedded JSON string."""
    detail = {
        "eventCategory": "Management",
        "sourceIPAddress": "203.0.113.4",
        "userAgent": "aws-cli/2.15.0",
        "awsRegion": "us-east-1",
        "userIdentity": {
            "type": "IAMUser",
            "arn": "arn:aws:iam::123456789012:user/dana",
            "userName": "dana",
            "sessionContext": {"attributes": {"mfaAuthenticated": "true"}},
        },
    }
    detail.update(overrides.pop("detail", {}))
    event = {
        "EventId": "e-1",
        "EventName": "ConsoleLogin",
        "EventSource": "signin.amazonaws.com",
        "EventTime": datetime(2026, 9, 1, 12, 30, tzinfo=timezone.utc),
        "Username": "dana",
        "CloudTrailEvent": json.dumps(detail),
    }
    event.update(overrides)
    return event


# -- The registry --------------------------------------------------------------


def test_provider_for_returns_each_provider():
    assert provider_for("aws").name == "aws"
    assert provider_for("azure").name == "azure"
    assert provider_for("gcp").name == "gcp"


def test_an_unknown_provider_name_raises_rather_than_collecting_nothing():
    with pytest.raises(KeyError):
        provider_for("digitalocean")


# -- user_activity -------------------------------------------------------------


def test_user_activity_maps_a_cloudtrail_event_to_atds_row(ctx):
    provider = aws_with(
        {"cloudtrail": FakeClient(lookup_events={"Events": [trail_event()]})}
    )

    result = provider.user_activity(ctx, ACCOUNT)

    assert result.outcome is Outcome.OK
    (row,) = result.data
    # `id` is what ATD upserts on -- not `remote_id`, which is its column name.
    assert row["id"] == "e-1"
    assert row["event_time"] == "2026-09-01T12:30:00+00:00"
    assert row["event_name"] == "ConsoleLogin"
    assert row["user_arn"] == "arn:aws:iam::123456789012:user/dana"
    assert row["user_type"] == "IAMUser"
    assert row["source_ip"] == "203.0.113.4"
    assert row["mfa_used"] is True
    assert row["success"] is True


def test_mfa_is_false_not_none_when_cloudtrail_says_the_string_false(ctx):
    detail = {
        "userIdentity": {
            "sessionContext": {"attributes": {"mfaAuthenticated": "false"}}
        }
    }
    provider = aws_with(
        {
            "cloudtrail": FakeClient(
                lookup_events={"Events": [trail_event(detail=detail)]}
            )
        }
    )

    (row,) = provider.user_activity(ctx, ACCOUNT).data

    # CloudTrail writes booleans as strings; `bool("false")` is True, which
    # would report every un-MFA'd sign-in as MFA-protected.
    assert row["mfa_used"] is False


def test_an_event_with_an_error_code_is_not_a_success(ctx):
    provider = aws_with(
        {
            "cloudtrail": FakeClient(
                lookup_events={
                    "Events": [trail_event(detail={"errorCode": "AccessDenied"})]
                }
            )
        }
    )

    (row,) = provider.user_activity(ctx, ACCOUNT).data

    assert row["success"] is False
    assert row["details"]["errorCode"] == "AccessDenied"


def test_a_malformed_event_payload_costs_its_detail_not_the_sweep(ctx):
    broken = trail_event(CloudTrailEvent="{not json")
    provider = aws_with(
        {
            "cloudtrail": FakeClient(
                lookup_events={"Events": [broken, trail_event(EventId="e-2")]}
            )
        }
    )

    result = provider.user_activity(ctx, ACCOUNT)

    assert result.outcome is Outcome.OK
    assert [row["id"] for row in result.data] == ["e-1", "e-2"]
    assert result.data[0]["user_arn"] is None  # lost with the bad JSON
    assert result.data[1]["user_arn"] is not None  # the good one is intact


def test_an_account_with_no_events_is_ok_and_empty_not_failed(ctx):
    provider = aws_with({"cloudtrail": FakeClient(lookup_events={"Events": []})})

    result = provider.user_activity(ctx, ACCOUNT)

    # "Collected nothing" and "never ran" must not look alike (`F18`).
    assert result.outcome is Outcome.OK
    assert result.data == []


def test_the_lookup_window_is_pinned_to_midnight(ctx):
    account = CloudAccount(
        provider="aws", account="1", start=date(2026, 1, 1), end=date(2026, 2, 1)
    )

    start, end = _window(account)

    # Same trap as `D42` in the git window: a bare date handed to something
    # that fills in the current time of day makes the same scan of the same
    # account return a different span depending on the hour it ran.
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert (end.hour, end.minute, end.second) == (0, 0, 0)
    assert start.tzinfo is timezone.utc


# -- load_balancers ------------------------------------------------------------


def elbv2_client(region):
    return FakeClient(
        describe_load_balancers={
            "LoadBalancers": [
                {
                    "LoadBalancerArn": "arn:aws:elasticloadbalancing:...:lb/app/web/abc",
                    "LoadBalancerName": "web",
                    "DNSName": "web-123.us-east-1.elb.amazonaws.com",
                    "Type": "application",
                    "Scheme": "internet-facing",
                    "State": {"Code": "active"},
                    "VpcId": "vpc-1",
                    "IpAddressType": "ipv4",
                    "CreatedTime": datetime(2026, 3, 4, tzinfo=timezone.utc),
                    "AvailabilityZones": [
                        {"ZoneName": "us-east-1a", "SubnetId": "subnet-1"}
                    ],
                    "SecurityGroups": ["sg-1"],
                }
            ]
        },
        describe_listeners={
            "Listeners": [{"Port": 80, "Protocol": "HTTP", "SslPolicy": None}]
        },
    )


def elb_client(region):
    return FakeClient(
        describe_load_balancers={
            "LoadBalancerDescriptions": [
                {
                    "LoadBalancerName": "legacy",
                    "DNSName": "legacy-9.us-east-1.elb.amazonaws.com",
                    "Scheme": "internal",
                    "VPCId": "vpc-1",
                    "AvailabilityZones": ["us-east-1a"],
                    "Instances": [{"InstanceId": "i-1"}, {"InstanceId": "i-2"}],
                    "ListenerDescriptions": [
                        {"Listener": {"LoadBalancerPort": 443, "Protocol": "HTTPS"}}
                    ],
                }
            ]
        }
    )


def test_load_balancers_collects_both_the_v2_and_classic_apis(ctx):
    provider = aws_with({"elbv2": elbv2_client, "elb": elb_client})

    result = provider.load_balancers(ctx, ACCOUNT)

    assert result.outcome is Outcome.OK
    modern, classic = result.data
    assert modern["lb_type"] == "application"
    assert modern["scheme"] == "internet-facing"
    assert modern["listeners"] == [{"port": 80, "protocol": "HTTP", "ssl_policy": None}]
    assert modern["availability_zones"] == ["us-east-1a"]
    assert modern["subnets"] == ["subnet-1"]
    assert classic["lb_type"] == "classic"
    assert classic["target_count"] == 2


def test_a_classic_balancers_id_is_qualified_by_region(ctx):
    provider = aws_with(
        {
            "elbv2": lambda r: FakeClient(
                describe_load_balancers={"LoadBalancers": []}
            ),
            "elb": elb_client,
        },
        regions=("us-east-1", "eu-west-1"),
    )

    ids = [row["id"] for row in provider.load_balancers(ctx, ACCOUNT).data]

    # Classic ELBs have no ARN, and names are only unique within a region.
    # Unqualified, two same-named balancers collapse onto one ATD row, since
    # the upsert key is (report, provider, account, remote_id).
    assert ids == ["classic/us-east-1/legacy", "classic/eu-west-1/legacy"]
    assert len(set(ids)) == 2


# -- The region sweep ----------------------------------------------------------


def refusing(region):
    raise RuntimeError(f"AuthFailure in {region}")


def test_one_refusing_region_does_not_lose_the_others(ctx):
    def elbv2(region):
        if region == "ap-east-1":
            refusing(region)
        return elbv2_client(region)

    provider = aws_with(
        {
            "elbv2": elbv2,
            "elb": lambda r: FakeClient(
                describe_load_balancers={"LoadBalancerDescriptions": []}
            ),
        },
        regions=("us-east-1", "ap-east-1"),
    )

    result = provider.load_balancers(ctx, ACCOUNT)

    # Opt-in regions refuse routinely; that is not a failed inventory.
    assert result.outcome is Outcome.OK
    assert len(result.data) == 1


def test_every_region_refusing_is_failed_not_an_empty_inventory(ctx):
    provider = aws_with(
        {"elbv2": refusing, "elb": refusing}, regions=("us-east-1", "eu-west-1")
    )

    result = provider.load_balancers(ctx, ACCOUNT)

    # The distinction `_check_coverage` exists to protect: an inventory that
    # collected nothing because every call raised is a FAILED artifact, not
    # an account with no load balancers.
    assert result.outcome is Outcome.FAILED
    assert "AuthFailure" in result.error


def test_a_session_that_cannot_be_built_fails_rather_than_raising(ctx):
    def explode(account):
        raise RuntimeError("ProfileNotFound: no such profile 'prod'")

    result = AwsProvider(session_factory=explode).user_activity(ctx, ACCOUNT)

    assert result.outcome is Outcome.FAILED
    assert "ProfileNotFound" in result.error


# -- The orchestrator ----------------------------------------------------------


def test_unported_artifacts_are_skipped_with_a_reason_not_reported_empty(ctx):
    provider = aws_with({})

    for artifact in (Artifact.COSTS, Artifact.INSTANCES, Artifact.STORAGE):
        result = getattr(provider, artifact.value)(ctx, ACCOUNT)
        assert result.outcome is Outcome.SKIPPED
        assert result.error


def test_scan_cloud_returns_one_result_per_artifact(ctx):
    results = Scanner(ScanConfig(write_files=False))._scan_cloud(ctx, ACCOUNT)

    assert [r.artifact for r in results] == list(CLOUD_ARTIFACTS)
    assert all(r.target == ACCOUNT.account for r in results)


def test_an_unknown_provider_fails_every_artifact_and_loses_none(ctx):
    account = CloudAccount.model_construct(provider="digitalocean", account="1")

    results = Scanner(ScanConfig(write_files=False))._scan_cloud(ctx, account)

    assert len(results) == len(CLOUD_ARTIFACTS)
    assert all(r.outcome is Outcome.FAILED for r in results)
    assert all("digitalocean" in r.error for r in results)


class StubProvider:
    """A provider with a deterministic ``available()``.

    The orchestrator tests must not depend on whether the AWS SDK happens to
    be installed: CI installs ``.[dev]`` and has boto3, a lean dev venv does
    not, and a test that quietly changes behaviour between the two is worth
    less than no test.
    """

    name = "aws"

    def __init__(self, available=True, raises=None):
        self._available = available
        self._raises = raises

    def available(self, ctx):
        return self._available

    def _artifact(self, artifact, account):
        if self._raises == artifact:
            raise RuntimeError("boom")
        return ok(artifact, account, [])

    def costs(self, ctx, account):
        return self._artifact(Artifact.COSTS, account)

    def instances(self, ctx, account):
        return self._artifact(Artifact.INSTANCES, account)

    def utilization(self, ctx, account):
        return self._artifact(Artifact.UTILIZATION, account)

    def storage(self, ctx, account):
        return self._artifact(Artifact.STORAGE, account)

    def user_activity(self, ctx, account):
        return self._artifact(Artifact.USER_ACTIVITY, account)

    def load_balancers(self, ctx, account):
        return self._artifact(Artifact.LOAD_BALANCERS, account)


def use_provider(monkeypatch, provider):
    monkeypatch.setattr("verinfast2.cloud.base.provider_for", lambda name: provider)


def test_a_provider_that_raises_loses_only_that_artifact(ctx, monkeypatch):
    use_provider(monkeypatch, StubProvider(raises=Artifact.STORAGE))

    results = Scanner(ScanConfig(write_files=False))._scan_cloud(ctx, ACCOUNT)

    by_artifact = {r.artifact: r for r in results}
    assert by_artifact[Artifact.STORAGE].outcome is Outcome.FAILED
    assert "boom" in by_artifact[Artifact.STORAGE].error
    # The other five still ran -- v1's single bare `except` lost everything
    # after the first failure (`F19`).
    assert len(results) == len(CLOUD_ARTIFACTS)
    assert by_artifact[Artifact.LOAD_BALANCERS].outcome is Outcome.OK


def test_a_missing_sdk_skips_every_artifact_with_a_reason(ctx, monkeypatch):
    use_provider(monkeypatch, StubProvider(available=False))

    results = Scanner(ScanConfig(write_files=False))._scan_cloud(ctx, ACCOUNT)

    assert len(results) == len(CLOUD_ARTIFACTS)
    assert all(r.outcome is Outcome.SKIPPED for r in results)
    assert all("not installed" in r.error for r in results)


def test_a_cloud_only_scan_runs_end_to_end(ctx, monkeypatch):
    use_provider(monkeypatch, StubProvider())
    config = ScanConfig(write_files=False, cloud=[ACCOUNT])

    result = Scanner(config).scan()

    assert len(result.artifacts) == len(CLOUD_ARTIFACTS)
    assert all(r.outcome is Outcome.OK for r in result.artifacts)
    # Every artifact that actually ran is timed.
    assert all(r.duration_seconds is not None for r in result.artifacts)


@pytest.mark.parametrize("name", ["azure", "gcp"])
@pytest.mark.parametrize("artifact", CLOUD_ARTIFACTS)
def test_the_unported_providers_skip_every_artifact_with_a_reason(ctx, name, artifact):
    provider = provider_for(name)

    result = getattr(provider, artifact.value)(ctx, ACCOUNT)

    # Not raising, and not an empty OK either: a provider nobody has written
    # yet must say so, or a scan of an Azure account reports six artifacts
    # that found nothing rather than six nobody collected (`F18`, `F19`).
    assert result.outcome is Outcome.SKIPPED
    assert result.error
    assert result.data is None


@pytest.mark.parametrize("name", ["azure", "gcp"])
def test_the_unported_providers_report_sdk_availability_without_importing(ctx, name):
    # A bool either way -- never a raise because the SDK is absent, which is
    # the normal case once the clouds move behind extras.
    assert isinstance(provider_for(name).available(ctx), bool)


def test_gcp_costs_does_not_claim_v1_had_them():
    # v1 collected no GCP costs at all, so "not ported from v1" would be a
    # false account of why the artifact is empty.
    from verinfast2.cloud.gcp import GcpProvider

    with scan_context(ScanConfig(write_files=False)) as context:
        result = GcpProvider().costs(context, ACCOUNT)

    assert "not ported" not in result.error
    assert "no GCP costs" in result.error
