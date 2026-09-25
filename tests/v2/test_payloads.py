"""Truncation is the privacy boundary, so it gets tested like one.

``truncate_findings`` is what stops customer source leaving the machine
(`S2`). ATD serves it on by default and so do we, which means these tests are
about what *survives* as much as what is cut.
"""

from __future__ import annotations

import copy

import pytest

import atd_fixtures as fx
from verinfast2.transport.payloads import (
    NO_TRUNCATE,
    cloud_envelope,
    truncate,
    truncate_findings,
)

# -- What gets cut ----------------------------------------------------------


def test_the_matched_source_line_is_truncated():
    """``extra.lines`` is the one field that holds customer code verbatim."""
    findings = copy.deepcopy(fx.FINDINGS_PAYLOAD)
    findings["results"][0]["extra"]["lines"] = "eval(secret_business_logic())" * 10

    out = truncate_findings(findings, max_length=10)

    assert out["results"][0]["extra"]["lines"] == "eval(secre"


def test_nested_strings_are_reached():
    out = truncate({"a": {"b": ["cccccccccc"]}}, max_length=3)

    assert out == {"a": {"b": ["ccc"]}}


def test_numbers_and_booleans_pass_through_unchanged():
    """Coercing them would change the shape ATD validates against."""
    out = truncate(
        {"line": 10, "ok": True, "ratio": 0.25, "nothing": None}, max_length=1
    )

    assert out == {"line": 10, "ok": True, "ratio": 0.25, "nothing": None}


def test_a_non_positive_max_length_removes_strings_entirely():
    """A legitimate "send no source at all" setting, not an edge case."""
    assert truncate({"lines": "secret"}, max_length=0) == {"lines": ""}


# -- What survives ----------------------------------------------------------


@pytest.mark.parametrize("key", sorted(NO_TRUNCATE))
def test_excluded_keys_survive_in_full(key: str):
    """These are identifiers and classifications, not code. Cutting a rule id
    to 30 characters makes it match nothing."""
    long = "x" * 200
    out = truncate({key: long}, max_length=5)

    assert out[key] == long


def test_a_full_check_id_survives_truncation():
    out = truncate_findings(copy.deepcopy(fx.FINDINGS_PAYLOAD), max_length=5)

    assert out["results"][0]["check_id"] == "python.lang.security.audit.eval-detected"


def test_an_excluded_keys_nested_list_survives_whole():
    """``owasp`` is a list of strings under an excluded key — the exclusion
    covers the whole value, not just a top-level string."""
    out = truncate({"owasp": ["A03:2021 – Injection", "A01:2021"]}, max_length=3)

    assert out["owasp"] == ["A03:2021 – Injection", "A01:2021"]


def test_the_finding_message_survives():
    """The message is the rule's own English, not the customer's code."""
    out = truncate_findings(copy.deepcopy(fx.FINDINGS_PAYLOAD), max_length=3)

    assert out["results"][0]["extra"]["message"] == "Detected use of eval()."


def test_the_path_survives():
    """ATD keys code files on it; a cut path orphans the finding."""
    out = truncate_findings(copy.deepcopy(fx.FINDINGS_PAYLOAD), max_length=3)

    assert out["results"][0]["path"] == "src/engine.py"


# -- Purity -----------------------------------------------------------------


def test_truncation_does_not_mutate_its_input():
    """v1's ``truncate_children`` mutated in place, which is why the same
    findings object could not be both uploaded and rendered locally (`D19`)."""
    findings = copy.deepcopy(fx.FINDINGS_PAYLOAD)
    before = copy.deepcopy(findings)

    truncate_findings(findings, max_length=1)

    assert findings == before


def test_disabled_truncation_returns_the_payload_untouched():
    findings = copy.deepcopy(fx.FINDINGS_PAYLOAD)

    assert truncate_findings(findings, enabled=False, max_length=1) == findings


# -- The cloud envelope -----------------------------------------------------


def test_cloud_envelope_matches_the_shape_atd_asserts():
    assert cloud_envelope("aws", "123456789012", []) == {
        "metadata": {"provider": "aws", "account": "123456789012"},
        "data": [],
    }


def test_cloud_envelope_round_trips_the_fixture_rows():
    rows = fx.COSTS_PAYLOAD["data"]

    assert cloud_envelope("aws", "123456789012", rows) == fx.COSTS_PAYLOAD
