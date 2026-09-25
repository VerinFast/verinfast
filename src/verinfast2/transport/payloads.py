"""Shaping artifacts for the wire, immediately before they go.

Two jobs, and nothing else:

1. **Truncation** — cut the source snippets out of a findings payload so the
   customer's code does not leave the machine (`S2`). This is the privacy
   boundary, and it belongs here rather than in the findings scanner: the
   scanner's job is to find things, and a local HTML report wants the
   untruncated text.
2. **The cloud envelope** — the ``{"metadata": …, "data": […]}`` wrapper
   every cloud route expects.

Everything here is a pure function returning a new object. v1's
``truncate_children`` mutated the dict it was handed, which is why the same
findings object could not be both uploaded and rendered into the local
report (`D19`).
"""

from __future__ import annotations

from typing import Any, Final

from verinfast2.models import Provider

#: Keys whose values are never truncated.
#:
#: These are identifiers and classifications, not code: cutting them to 30
#: characters turns ``"CWE-95: Eval Injection"`` into ``"CWE-95: Eval Inject"``
#: and a rule id into something that matches nothing. The set is v1's,
#: unchanged — ATD has been ingesting findings shaped by it for two years, and
#: widening it is a data-comparability decision, not a refactor.
NO_TRUNCATE: Final[frozenset[str]] = frozenset(
    {
        "check_id",
        "cwe",
        "fingerprint",
        "license",
        "message",
        "owasp",
        "path",
        "references",
        "severity",
        "source",
        "url",
    }
)

#: The key that actually carries customer source. Named for the docs' sake;
#: it is truncated because it is *not* in :data:`NO_TRUNCATE`.
SOURCE_KEY: Final = "lines"


def truncate(
    value: Any, *, max_length: int = 30, exclude: frozenset[str] = NO_TRUNCATE
) -> Any:
    """Cap every string in a nested structure, except under *exclude* keys.

    Returns a new structure; the input is not modified.

    An excluded key's whole value is preserved, nested containers included —
    so ``metadata.owasp`` survives as a list of full strings while
    ``extra.lines``, which holds the matched source, is cut:

        >>> truncate({"lines": "eval(user_input) # " + "x" * 80}, max_length=10)
        {'lines': 'eval(user_'}
        >>> truncate({"owasp": ["A03:2021 – Injection"]})
        {'owasp': ['A03:2021 – Injection']}

    Args:
        value: any JSON-shaped object.
        max_length: characters to keep. Non-positive removes strings
            entirely, which is a legitimate "send nothing" setting.
        exclude: keys whose values pass through untouched.
    """
    if isinstance(value, str):
        return value[:max_length] if max_length > 0 else ""
    if isinstance(value, dict):
        return {
            key: (
                item
                if key in exclude
                else truncate(item, max_length=max_length, exclude=exclude)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            truncate(item, max_length=max_length, exclude=exclude) for item in value
        ]
    # int, float, bool, None — nothing to cut, and coercing them would
    # change the shape ATD validates against.
    return value


def truncate_findings(
    findings: Any, *, enabled: bool = True, max_length: int = 30
) -> Any:
    """Apply :func:`truncate` to a findings payload when configured to.

    Kept separate so the call site reads as the policy it is. ATD serves
    ``truncate_findings: true`` by default and so do we (`S2`, Q9).
    """
    if not enabled:
        return findings
    return truncate(findings, max_length=max_length)


def cloud_envelope(
    provider: Provider, account: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Wrap cloud rows in the envelope every cloud route expects.

        >>> cloud_envelope("aws", "123456789012", [])
        {'metadata': {'provider': 'aws', 'account': '123456789012'}, 'data': []}

    ATD upserts on ``(report_id, provider, account, remote_id)``, so both
    metadata fields are part of the key — an envelope with the wrong account
    silently merges two accounts' inventories into one.
    """
    return {
        "metadata": {"provider": provider, "account": account},
        "data": rows,
    }
