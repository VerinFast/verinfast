"""Filling in licences and descriptions from public package registries.

A manifest usually names a package and a version and nothing else. The
``license`` and ``summary`` fields ATD stores come from the ecosystem's
registry — npm, RubyGems, NuGet, PyPI.

**This makes outbound calls during a scan**, which is worth being explicit
about in an agent whose premise is that it runs inside someone else's
perimeter. What leaves is the package name and version, not source; it goes
to the ecosystem's own public registry, the same host the project's package
manager already contacts. It is on by default, matching v1, and
``PrivacyConfig.enrich_dependencies`` turns it off — in which case licences
come from whatever the local manifest or lockfile already carries.

Two things v1 got wrong here:

- **No timeout.** ``httpx.Client(http2=True, timeout=None)`` means a registry
  that accepts a connection and then stalls hangs the scan forever, with no
  ceiling anywhere above it (`L10`, `S10`).
- **A client per walker**, each built in ``__init__``, so constructing a
  walker opened a connection pool whether or not anything was fetched.

Failures are never fatal: a lookup that times out, 404s or returns junk
leaves the entry's licence unset, which is the honest answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import quote

#: Per-request ceiling. Registries are fast when healthy; a slow one is not
#: worth a scan's time budget, and there are as many requests as packages.
DEFAULT_TIMEOUT: Final = 10.0

#: Give up on a registry entirely after this many consecutive failures. A
#: blocked egress path should cost one timeout, not one per dependency.
FAILURE_BUDGET: Final = 5

NPM: Final = "https://registry.npmjs.org"
RUBYGEMS: Final = "https://rubygems.org"
NUGET_INDEX: Final = "https://api.nuget.org/v3/index.json"
PYPI: Final = "https://pypi.org"


def _clean(version: str | None) -> str:
    """A bare version from a specifier. ``"==1.2.3"`` becomes ``"1.2.3"``."""
    if not version:
        return ""
    return version.lstrip("=<>~^!").strip()


@dataclass
class RegistryClient:
    """Look up package metadata, with a budget and without ever raising.

    Args:
        client: an ``httpx.Client``. Injected in tests so the suite stays
            offline (`N16`); built lazily otherwise.
        enabled: ``False`` makes every lookup return ``{}`` without a
            request.
        timeout: per-request ceiling, seconds.
        failure_budget: consecutive failures tolerated per host before that
            host is abandoned for the rest of the scan.
    """

    client: Any = None
    enabled: bool = True
    timeout: float = DEFAULT_TIMEOUT
    failure_budget: int = FAILURE_BUDGET

    _failures: dict[str, int] = field(default_factory=dict, repr=False)
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _owns_client: bool = field(default=False, init=False, repr=False)
    #: NuGet publishes its real endpoints behind a discovery document.
    _nuget_registration: str | None = field(default=None, init=False, repr=False)
    _nuget_discovered: bool = field(default=False, init=False, repr=False)

    # -- Plumbing -------------------------------------------------------

    def _http(self):
        if self.client is None:
            import httpx

            self.client = httpx.Client(timeout=self.timeout, follow_redirects=True)
            self._owns_client = True
        return self.client

    def close(self) -> None:
        """Close a client this object created. One that was injected is not
        ours to close — the caller may still be using it."""
        if self._owns_client and self.client is not None:
            self.client.close()
            self.client = None
            self._owns_client = False

    def _host_of(self, url: str) -> str:
        return url.split("/")[2] if "//" in url else url

    def _get_json(self, url: str) -> dict[str, Any] | None:
        """One GET, decoded. ``None`` on anything at all going wrong."""
        if not self.enabled:
            return None
        host = self._host_of(url)
        if self._failures.get(host, 0) >= self.failure_budget:
            # Egress to this registry is evidently blocked or down. Paying
            # the timeout once per dependency would dominate the scan.
            return None
        if url in self._cache:
            return self._cache[url]

        try:
            response = self._http().get(url, timeout=self.timeout)
        except Exception:
            # Deliberately broad: a metadata lookup must never be able to
            # fail an artifact, whatever the transport does.
            self._failures[host] = self._failures.get(host, 0) + 1
            return None

        if response.status_code != 200:
            # A 404 is a real answer — the package is not there — and should
            # not count against a budget meant for connectivity problems.
            if response.status_code >= 500:
                self._failures[host] = self._failures.get(host, 0) + 1
            return None

        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return None

        self._failures[host] = 0
        if isinstance(data, dict):
            self._cache[url] = data
            return data
        return None

    # -- Per-ecosystem lookups ------------------------------------------

    def npm(self, name: str, version: str | None) -> dict[str, str]:
        """npm: ``/{name}/{version}`` returns that release's manifest."""
        clean = _clean(version)
        if not clean:
            return {}
        data = self._get_json(f"{NPM}/{quote(name, safe='@/')}/{quote(clean)}")
        if not data:
            return {}
        return _pick(license=_npm_license(data), summary=data.get("description"))

    def rubygems(self, name: str, version: str | None) -> dict[str, str]:
        clean = _clean(version)
        if not clean:
            return {}
        data = self._get_json(
            f"{RUBYGEMS}/api/v2/rubygems/{quote(name)}/versions/{quote(clean)}.json"
        )
        if not data:
            return {}
        licenses = data.get("licenses")
        if isinstance(licenses, list):
            licenses = ", ".join(str(item) for item in licenses if item)
        return _pick(license=licenses, summary=data.get("summary") or data.get("info"))

    def pypi(self, name: str, version: str | None) -> dict[str, str]:
        clean = _clean(version)
        url = (
            f"{PYPI}/pypi/{quote(name)}/{quote(clean)}/json"
            if clean
            else f"{PYPI}/pypi/{quote(name)}/json"
        )
        data = self._get_json(url)
        if not data:
            return {}
        info = data.get("info") or {}
        if not isinstance(info, dict):
            return {}
        return _pick(license=info.get("license"), summary=info.get("summary"))

    def nuget(self, name: str, version: str | None) -> dict[str, str]:
        """NuGet needs two hops: a registration blob, then its catalog entry.

        Package ids are case-insensitive but the registration URLs are
        lowercase, so v1 tried the given case and then retried lowercased.
        Lowercasing once is the same thing without the wasted round-trip.
        """
        clean = _clean(version)
        if not clean:
            return {}
        base = self._nuget_base()
        if not base:
            return {}
        data = self._get_json(f"{base}{quote(name.lower())}/{quote(clean)}.json")
        if not data:
            return {}
        catalog_url = data.get("catalogEntry")
        if not isinstance(catalog_url, str):
            return {}
        catalog = self._get_json(catalog_url)
        if not catalog:
            return {}
        return _pick(
            license=catalog.get("licenseExpression") or catalog.get("licenseUrl"),
            summary=catalog.get("description"),
        )

    def _nuget_base(self) -> str | None:
        """The registration base URL, fetched once per scan."""
        if self._nuget_discovered:
            return self._nuget_registration
        self._nuget_discovered = True
        index = self._get_json(NUGET_INDEX)
        for resource in (index or {}).get("resources") or []:
            if isinstance(resource, dict) and resource.get("@type") == (
                "RegistrationsBaseUrl"
            ):
                self._nuget_registration = resource.get("@id")
                break
        return self._nuget_registration


def _npm_license(data: dict[str, Any]) -> str | None:
    """npm's ``license`` is a string, a ``{"type": ...}`` dict, or a list."""
    value = data.get("license")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("type")
    if isinstance(value, list):
        parts = [
            item.get("type") if isinstance(item, dict) else str(item) for item in value
        ]
        return " ".join(part for part in parts if part) or None
    return None


def _pick(**fields: Any) -> dict[str, str]:
    """Keep only the fields that have a usable value.

    v1 wrote the strings ``"License not available"`` and ``"No description
    provided."`` into the payload on a failed lookup, so ATD stores those as
    though they were licences. An unknown licence is an absent key.
    """
    return {
        key: str(value).strip()
        for key, value in fields.items()
        if value and str(value).strip()
    }
