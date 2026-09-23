"""Building a :class:`~verinfast2.config.schema.ScanConfig` from somewhere.

Four sources, one shape. Each is an explicit call — nothing here runs because
a module was imported.

The YAML key names are ATD v3's: its ``services/code_scan.py`` emits exactly
this document at ``GET /api/agent/config/{uuid}/VerinFastConfig.yaml``, so the
reader must keep accepting them unchanged (`A7`, `F11`)::

    baseurl: https://atd.example/api
    should_upload: true
    dry: false
    truncate_findings: true
    truncate_findings_length: 30
    report:
      uuid: 9a6e8696-…
    server:
      code_separator: /CodeScan
    modules:
      code:
        git:
          start: '2025-03-01'
        dependencies: true
      cloud:
        - provider: aws
          account: '123456789012'
          start: '2025-03-01'
          end: '2025-09-23'
    repos:
      - https://github.com/example/app.git
    local_repos:
      - /srv/checkouts/app

Three behaviours are load-bearing and each fixes a v1 defect:

- **``modules.code.git.start`` is honoured.** v1 read it into
  ``self.modules.code.git.start`` and then looked for it somewhere else, so
  the configured window was silently ignored and every scan walked all of
  history (`D1`). ATD knows this and sends its preferred window anyway,
  "for forward compatibility"; this is the forward compatibility.
- **``report.uuid`` implies uuid addressing.** Its presence is what sets
  ``upload.uuid``, exactly as v1 inferred it.
- **``repos`` absent and ``repos: []`` are different.** ATD only emits the
  key when non-empty, precisely because an explicit empty list suppresses
  the scan-the-working-directory fallback. Preserve the distinction.

Anything ATD may add later is ignored rather than rejected: a served config
is an input from another team's deploy cadence, and a new key must not take
an agent down in the field. Keys *we* recognise are validated strictly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from verinfast2.config.schema import CodeConfig, PrivacyConfig, ScanConfig
from verinfast2.models import CloudAccount, ScanTarget
from verinfast2.transport.paths import UploadConfig

__all__ = ["from_dict", "from_file", "from_url", "from_yaml"]


def _as_date(value: Any) -> date | None:
    """Accept a ``date``, an ISO string, or nothing. Never raise on junk."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _repo_name(url: str) -> str:
    """The name ATD will key the repository row on.

    A cloned remote keeps its ``.git`` suffix — that is what v1 sent and what
    ATD's rows already carry, so dropping it would orphan every historical
    repository. A local path uses the directory basename, bare.
    """
    return url.rstrip("/").rsplit("/", 1)[-1]


def _targets(document: dict[str, Any]) -> list[ScanTarget]:
    """Remote repos first, then local checkouts — v1's upload order."""
    targets: list[ScanTarget] = []
    for url in document.get("repos") or []:
        if not isinstance(url, str) or not url:
            continue
        targets.append(ScanTarget(name=_repo_name(url), url=url))
    for raw in document.get("local_repos") or []:
        if not isinstance(raw, str) or not raw:
            continue
        path = Path(raw).expanduser()
        targets.append(ScanTarget(name=path.name or str(path), path=path))
    return targets


def _cloud(document: dict[str, Any]) -> list[CloudAccount]:
    accounts: list[CloudAccount] = []
    modules = document.get("modules") or {}
    for entry in modules.get("cloud") or []:
        if not isinstance(entry, dict):
            continue
        provider = entry.get("provider")
        account = entry.get("account")
        if provider not in ("aws", "azure", "gcp") or account is None:
            continue
        accounts.append(
            CloudAccount(
                provider=provider,
                # ATD emits account ids as strings; a YAML scalar that looks
                # numeric would otherwise arrive as an int and stop matching
                # the upsert key.
                account=str(account),
                profile=entry.get("profile"),
                start=_as_date(entry.get("start")),
                end=_as_date(entry.get("end")),
            )
        )
    return accounts


def from_dict(document: dict[str, Any]) -> ScanConfig:
    """Build a config from a parsed agent-config document.

    Unknown top-level keys are ignored (see the module docstring). A missing
    key always falls back to the :class:`ScanConfig` default rather than to
    ``None``, so a sparse served config and a hand-written one behave the
    same.
    """
    if not isinstance(document, dict):
        raise TypeError(
            f"agent config must be a mapping, got {type(document).__name__}"
        )

    report = document.get("report") or {}
    report_uuid = report.get("uuid") if isinstance(report, dict) else None
    report_id = report_uuid if report_uuid else document.get("report_id")

    server = document.get("server") or {}
    if not isinstance(server, dict):
        server = {}
    upload_kwargs: dict[str, Any] = {"uuid": bool(report_uuid)}
    for key in ("prefix", "code_separator", "cost_separator"):
        if key in server:
            upload_kwargs[key] = server[key]

    modules = document.get("modules") or {}
    code_module = modules.get("code") if isinstance(modules, dict) else None
    code_module = code_module if isinstance(code_module, dict) else {}

    code: dict[str, Any] = {}
    git_module = code_module.get("git")
    if isinstance(git_module, dict):
        git_start = _as_date(git_module.get("start"))
        if git_start is not None:
            # The line that fixes D1.
            code["git_start"] = git_start
    elif git_module is False:
        code["git"] = False
    if "dependencies" in code_module:
        code["dependencies"] = bool(code_module["dependencies"])
    for key in ("sizes", "stats", "findings"):
        if key in code_module:
            code[key] = bool(code_module[key])

    privacy: dict[str, Any] = {}
    if "truncate_findings" in document:
        privacy["truncate_findings"] = bool(document["truncate_findings"])
    if "truncate_findings_length" in document:
        privacy["truncate_findings_length"] = int(document["truncate_findings_length"])

    # ``dry`` and ``should_upload`` are separate switches in the served
    # document and either one alone turns uploading off.
    should_upload = bool(document.get("should_upload", False)) and not bool(
        document.get("dry", False)
    )

    fields: dict[str, Any] = {
        "targets": _targets(document),
        "cloud": _cloud(document),
        "base_url": document.get("baseurl"),
        "report_id": report_id,
        "upload": UploadConfig(**upload_kwargs),
        "should_upload": should_upload,
    }
    # Unset fields take their model defaults, so a sparse served config and a
    # hand-written one produce the same object.
    if code:
        fields["code"] = CodeConfig(**code)
    if privacy:
        fields["privacy"] = PrivacyConfig(**privacy)
    if "exclude" in document and isinstance(document["exclude"], list):
        fields["exclude"] = [str(item) for item in document["exclude"]]

    return ScanConfig(**fields)


def from_yaml(text: str) -> ScanConfig:
    """Parse an agent-config YAML document. Wraps :func:`from_dict`.

    ``yaml.safe_load`` only — a served config is remote input, and
    ``yaml.load`` on it would be arbitrary object construction from the
    network (`S6`).
    """
    import yaml

    return from_dict(yaml.safe_load(text) or {})


def from_file(path: str | Path) -> ScanConfig:
    """Read and parse a local agent-config file."""
    return from_yaml(Path(path).read_text(encoding="utf-8"))


def from_url(url: str, *, timeout: float = 30.0) -> ScanConfig:
    """Fetch and parse a served agent config.

    Unlike v1, the document is parsed in memory and never written to the
    working directory — it carries the report UUID, which is the upload
    credential (`S5`, `D6`).
    """
    import httpx

    response = httpx.get(url, timeout=timeout, follow_redirects=False)
    response.raise_for_status()
    return from_yaml(response.text)
