"""What a dependency scan produces.

One flat array of entries is what ATD ingests, and ``name`` and ``source`` are
the only required fields — everything else is optional and omitted when empty,
because ATD's ingest treats a missing key and an empty string differently.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class Entry(BaseModel):
    """One dependency, in the shape ATD stores.

    v1's ``Entry`` subclassed ``dict`` while also setting instance attributes,
    so it was a dict that never contained any of its own data — every use had
    to remember to call ``to_json()`` first (`D28`). This is a plain model and
    :meth:`payload` is explicit.

    Args:
        name: the package name. Required; an entry without one is a bug in a
            parser, not a dependency.
        source: the ecosystem or registry it came from. Also required — ATD
            groups on it, and two ecosystems can share a package name.
        specifier: a version or PEP 440-style range, verbatim from the
            manifest. Never normalised: ``==1.2.3`` and ``^1.2`` mean
            different things and ATD stores both.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    specifier: str | None = None
    license: str | None = None
    summary: str | None = None
    requires: list[str] | None = None
    required_by: str | list[str] | None = None

    @field_validator("name", "source")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("entries must have a package name and a source")
        return value

    def payload(self) -> dict[str, Any]:
        """The wire form: required keys always, optional keys only when set.

        ATD distinguishes an absent key from an empty one, so an unknown
        licence is omitted rather than sent as ``""``.
        """
        data: dict[str, Any] = {"name": self.name, "source": self.source}
        for field in ("specifier", "license", "summary", "requires", "required_by"):
            value = getattr(self, field)
            if value:
                data[field] = value
        return data
