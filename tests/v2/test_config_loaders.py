"""Reading the config ATD serves.

``GET /api/agent/config/{uuid}/VerinFastConfig.yaml`` is the first call a real
agent makes, and everything after it depends on parsing the answer correctly.
Three of these tests pin defects v1 shipped for years.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

import atd_fixtures as fx
from verinfast2.config.loaders import from_dict, from_file, from_url, from_yaml


@pytest.fixture
def served():
    return from_yaml(fx.SERVED_CONFIG_YAML)


# -- The served document ----------------------------------------------------


def test_report_uuid_becomes_the_report_id_and_turns_on_uuid_addressing(served):
    assert served.report_id == "9a6e8696-f93a-4402-a64e-342ccb37592b"
    assert served.upload.uuid is True


def test_code_separator_is_taken_from_the_server_block(served):
    """ATD pins this explicitly in every served config because agents in the
    field predate the default being fixed."""
    assert served.upload.code_separator == "/CodeScan"


def test_base_url_comes_from_baseurl(served):
    assert served.base_url == "https://atd.example/api"


def test_should_upload_is_honoured(served):
    assert served.should_upload is True


def test_truncation_settings_are_honoured(served):
    assert served.privacy.truncate_findings is True
    assert served.privacy.truncate_findings_length == 30


def test_repos_and_local_repos_both_become_targets(served):
    assert [t.name for t in served.targets] == [
        "sample-app.git",
        "my-local-checkout",
    ]


def test_a_remote_target_carries_its_url_and_a_local_one_its_path(served):
    remote, local = served.targets
    assert remote.url == "https://github.com/example/sample-app.git"
    assert remote.path is None
    assert local.path is not None
    assert local.url is None


def test_cloud_accounts_are_parsed_with_their_window(served):
    assert len(served.cloud) == 1
    account = served.cloud[0]
    assert account.provider == "aws"
    assert account.account == "123456789012"
    assert account.start == date(2025, 3, 1)
    assert account.end == date(2025, 9, 23)


# -- D1: the git start date v1 dropped on the floor -------------------------


def test_git_start_is_actually_honoured():
    """v1 read ``modules.code.git.start`` into one attribute and looked for
    it under another, so every scan walked all of history regardless (`D1`).
    ATD sends the window anyway, "for forward compatibility" — this is it."""
    config = from_dict({"modules": {"code": {"git": {"start": "2024-01-15"}}}})

    assert config.code.git_start == date(2024, 1, 15)


def test_a_malformed_git_start_falls_back_rather_than_crashing():
    """A served config is another team's deploy cadence. A bad date should
    cost the configured window, not the whole scan."""
    config = from_dict({"modules": {"code": {"git": {"start": "not-a-date"}}}})

    assert config.code.git_start is not None


# -- The repos / repos:[] distinction ---------------------------------------


def test_an_absent_repos_key_leaves_targets_empty():
    assert from_dict({}).targets == []


def test_an_explicit_empty_repos_list_also_leaves_targets_empty():
    """ATD omits the key rather than sending ``[]`` precisely because the two
    mean different things to v1's cwd fallback. Both parse to no targets
    here; the difference lives in whatever decides the fallback."""
    assert from_dict({"repos": []}).targets == []


# -- dry / should_upload ----------------------------------------------------


def test_dry_run_turns_uploading_off_even_when_should_upload_is_true():
    config = from_dict({"should_upload": True, "dry": True})

    assert config.should_upload is False


def test_should_upload_false_turns_uploading_off():
    assert from_dict({"should_upload": False, "dry": False}).should_upload is False


def test_uploading_is_off_when_the_document_says_nothing():
    """Default to not sending data anywhere. The safe direction."""
    assert from_dict({}).should_upload is False


# -- Tolerance --------------------------------------------------------------


def test_an_unknown_top_level_key_is_ignored_not_rejected():
    """ATD ships on its own cadence; a new key must not take agents down."""
    config = from_dict({"some_future_atd_key": {"nested": True}})

    assert config.targets == []


def test_a_numeric_account_id_is_coerced_to_a_string():
    """An unquoted YAML account id arrives as an int and would stop matching
    ATD's ``(report, provider, account, remote_id)`` upsert key."""
    config = from_dict(
        {"modules": {"cloud": [{"provider": "aws", "account": 123456789012}]}}
    )

    assert config.cloud[0].account == "123456789012"


def test_a_cloud_entry_with_an_unknown_provider_is_dropped():
    config = from_dict(
        {
            "modules": {
                "cloud": [
                    {"provider": "aws", "account": "1"},
                    {"provider": "oracle", "account": "2"},
                ]
            }
        }
    )

    assert [a.provider for a in config.cloud] == ["aws"]


def test_an_empty_document_parses_to_defaults():
    assert from_yaml("").targets == []


def test_a_non_mapping_document_is_a_type_error():
    with pytest.raises(TypeError, match="must be a mapping"):
        from_dict(["not", "a", "mapping"])


# -- The other two entry points ---------------------------------------------


def test_from_file_reads_and_parses(tmp_path):
    path = tmp_path / "VerinFastConfig.yaml"
    path.write_text(fx.SERVED_CONFIG_YAML, encoding="utf-8")

    assert from_file(path).base_url == "https://atd.example/api"


def test_from_url_never_writes_the_document_to_disk(tmp_path, monkeypatch):
    """The document carries the report UUID, which is the upload credential.
    v1 saved it into the working directory and never deleted it, despite
    setting ``delete_config_after`` (`D6`, `S5`)."""
    monkeypatch.chdir(tmp_path)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=fx.SERVED_CONFIG_YAML)
    )
    monkeypatch.setattr(
        httpx, "get", lambda url, **kw: httpx.Client(transport=transport).get(url)
    )

    config = from_url("https://atd.example/api/agent/config/x/VerinFastConfig.yaml")

    assert config.report_id == "9a6e8696-f93a-4402-a64e-342ccb37592b"
    assert list(tmp_path.iterdir()) == []


def test_from_yaml_uses_safe_load():
    """A served config is remote input; ``yaml.load`` on it would be
    arbitrary object construction from the network (`S6`)."""
    import yaml

    with pytest.raises(yaml.constructor.ConstructorError):
        from_yaml("!!python/object/apply:os.system ['echo pwned']")


# -- Absent versus explicitly empty -----------------------------------------


def test_an_absent_repos_key_is_distinguishable_from_an_empty_one():
    """ATD emits `repos:` only when non-empty, because an explicit empty
    list suppresses the scan-the-cwd fallback and an absent key does not.
    `targets` alone cannot tell them apart, so the answer is recorded."""
    assert from_dict({}).targets_configured is False
    assert from_dict({"repos": []}).targets_configured is True
    assert from_dict({"local_repos": []}).targets_configured is True


def test_a_populated_list_also_counts_as_configured():
    config = from_dict({"repos": ["https://example.invalid/a.git"]})

    assert config.targets_configured is True
    assert len(config.targets) == 1


def test_the_served_config_is_configured(served):
    assert served.targets_configured is True


# -- A malformed value costs that setting, not the load ---------------------


@pytest.mark.parametrize("value", ["abc", None, [], {"a": 1}])
def test_a_malformed_truncation_length_falls_back_to_the_default(value):
    """`int(...)` raised and aborted the whole config load over one bad key,
    which is not the trade `_as_date` makes for dates."""
    config = from_dict({"truncate_findings_length": value})

    assert config.privacy.truncate_findings_length == 30


def test_a_numeric_string_truncation_length_is_still_accepted():
    assert (
        from_dict({"truncate_findings_length": "45"}).privacy.truncate_findings_length
        == 45
    )
