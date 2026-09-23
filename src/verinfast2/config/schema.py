"""The configuration object, and nothing that reads the environment.

Constructing a :class:`ScanConfig` never touches ``sys.argv``, never prompts,
never reads ``~``, and never opens a log file. That is the whole point: v1's
``Config.__init__`` parsed argv unless ``"pytest" in sys.argv[0]``, which is
the single hardest blocker on using VerinFast as a library (`L1`, `D31`).

Loading from a file, a URL or the command line lives in
:mod:`verinfast2.config.loaders` and :mod:`verinfast2.cli` respectively —
both of which *build* one of these and hand it over.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from verinfast2.models import CloudAccount, ScanTarget
from verinfast2.transport.paths import UploadConfig


def _default_git_start(today: date | None = None, months_back: int = 6) -> date:
    """First of the month, *months_back* months ago."""
    d = today or date.today()
    month, year = d.month - months_back, d.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


class CodeConfig(BaseModel):
    """What to collect from a repository."""

    model_config = ConfigDict(extra="forbid")

    git: bool = True
    sizes: bool = True
    stats: bool = True
    findings: bool = True
    dependencies: bool = True

    #: Earliest commit to collect. v1 read this from config and then dropped
    #: it on the floor (`D1`); here it is honoured.
    git_start: date = Field(default_factory=_default_git_start)

    #: Per-file size/LOC entries. Off makes a large repo much cheaper.
    per_file_detail: bool = True

    #: Run the scanned project's package manager (``npm install``,
    #: ``composer install``, ``gem install``) to resolve dependencies.
    #: **Off by default, and refused outright in library mode** — it executes
    #: arbitrary code from the dependency graph of the code being scanned
    #: (`S7`). Lockfile parsing covers most of what it bought.
    allow_package_manager_execution: bool = False


class PrivacyConfig(BaseModel):
    """What is allowed to leave the machine."""

    model_config = ConfigDict(extra="forbid")

    #: Cap every nested string in the findings payload. ATD serves this on by
    #: default; so do we (`S2`, Q9).
    truncate_findings: bool = True
    truncate_findings_length: int = 30

    #: POST run metadata to the vendor's telemetry endpoint. v1 did this
    #: unconditionally and undocumented (`S4`); here it is explicit, and
    #: library mode forces it off.
    telemetry: bool = False

    #: Upload the agent's own diagnostic logs.
    upload_logs: bool = False

    #: Look up licences and descriptions from public package registries
    #: (npm, PyPI, RubyGems, NuGet) for dependencies whose manifests do not
    #: carry them. On by default, matching v1.
    #:
    #: What leaves the machine is a package name and version, to that
    #: ecosystem's own public registry — the same host the project's package
    #: manager already contacts. Never source, never a path. Turning it off
    #: leaves licences to whatever the local manifest or lockfile records.
    enrich_dependencies: bool = True


class ScanConfig(BaseModel):
    """Everything one scan needs to know.

    Construct it directly, or via :mod:`verinfast2.config.loaders`.
    """

    model_config = ConfigDict(extra="forbid")

    targets: list[ScanTarget] = Field(default_factory=list)
    cloud: list[CloudAccount] = Field(default_factory=list)
    code: CodeConfig = Field(default_factory=CodeConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)

    # -- Server ---------------------------------------------------------
    base_url: str | None = None
    report_id: str | int | None = None
    upload: UploadConfig = Field(default_factory=UploadConfig)
    should_upload: bool = False

    # -- Filesystem, all injectable; none defaulted to ``~`` (`L7`, `S15`) --
    work_dir: Path | None = None
    output_dir: Path | None = None
    cache_dir: Path | None = None

    #: Write each artifact to ``output_dir`` as JSON as well as returning it.
    write_files: bool = True

    #: Library mode. Forbids prompting, telemetry, package-manager execution
    #: and writes to the home directory (`L5`, `L9`).
    embedded: bool = False

    exclude: list[str] = Field(
        default_factory=lambda: [
            "**/.git/**",
            "**/node_modules/**",
            "**/__pycache__/**",
            "build/**",
            "dist/**",
            "venv/**",
            "env/**",
        ]
    )

    #: Wall-clock ceiling for any single subprocess (`L10`, `S10`).
    subprocess_timeout_seconds: float = 900.0

    #: Per-request ceiling for a package-registry lookup. There is one
    #: request per dependency, so this is not the subprocess budget. v1 used
    #: ``timeout=None``, which lets a stalled registry hang a scan forever.
    registry_timeout_seconds: float = 10.0

    def for_library(self) -> ScanConfig:
        """A copy with every interactive or ambient behaviour disabled.

        :class:`~verinfast2.core.scanner.Scanner` applies this itself when
        ``embedded`` is set, so a caller cannot forget to.

        Registry enrichment is **not** turned off here. It is on by default
        in library mode too, which is a deliberate choice rather than an
        oversight: the licence data ATD stores comes from it. An embedded
        caller that does not want its worker making outbound calls per
        dependency sets ``privacy.enrich_dependencies=False`` — see
        :class:`~verinfast2.dependencies.registry.RegistryClient` for exactly
        what leaves the machine.

        Turns file writing off unless an ``output_dir`` was named explicitly.
        Without that, "writes nothing to the home directory" would only hold
        by accident — nothing else stops an artifact landing somewhere the
        caller never asked for. With it, an embedded scan that names no
        output directory writes no files at all, and one that does names
        where (`S15`, `L7`).
        """
        return self.model_copy(
            update={
                "embedded": True,
                "write_files": self.write_files and self.output_dir is not None,
                "privacy": self.privacy.model_copy(
                    update={"telemetry": False, "upload_logs": False}
                ),
                "code": self.code.model_copy(
                    update={"allow_package_manager_execution": False}
                ),
            }
        )
