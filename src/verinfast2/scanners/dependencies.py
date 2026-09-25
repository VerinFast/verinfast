"""Dependency and licence inventory across ecosystems.

Ports ``src/verinfast/dependencies/ (walk.py + walkers/)``. The walker
decomposition was the right shape; the base class was not. See
:mod:`verinfast2.dependencies` for the parsers and the traversal.

**One traversal, not nine.** Each v1 walker ran its own ``rglob("**/*")``
looking for its own manifest names, so a monorepo was walked once per
ecosystem (`N12`).

**No package-manager execution.** v1's ``npm install``, ``composer install``
and ``gem install -r --explain`` run arbitrary code from the dependency graph
of the code being scanned. That is defensible on a customer's laptop and is
remote code execution once ATD v3 imports us to scan untrusted samples
(`S7`, `S8`). Lockfiles cover the same ground: ``package-lock.json``,
``poetry.lock`` and ``Gemfile.lock`` are parsed in preference to the
manifests beside them, and carry resolved versions rather than ranges.

**One interface.** v1's base ``Walker.initialize(command)`` and its
subclasses' ``initialize(root_path)`` — and ``NuGetWalker.initialize()`` with
no argument at all — were three different methods sharing a name (`D27`).
There is no ``initialize`` here; a parser is a function.

Registry enrichment (licences and descriptions the files do not carry) is on
by default and configurable — see
:class:`~verinfast2.dependencies.registry.RegistryClient` for what leaves the
machine and :attr:`PrivacyConfig.enrich_dependencies` for turning it off.

Output stays a flat array of entries with ``name`` and ``source`` required.
"""

from __future__ import annotations

from verinfast2.core.context import ScanContext
from verinfast2.dependencies.registry import RegistryClient
from verinfast2.dependencies.walk import Walk
from verinfast2.models import Artifact, ArtifactResult, Outcome, ScanTarget


class DependencyScanner:
    """Collect declared and resolved dependencies for one target.

    Args:
        registry: the enrichment client. Built from config when omitted;
            injected in tests so the suite never opens a socket (`N16`).
    """

    artifact = Artifact.DEPENDENCIES

    def __init__(self, registry: RegistryClient | None = None) -> None:
        self._registry = registry

    def enabled(self, ctx: ScanContext) -> bool:
        return ctx.config.code.dependencies

    def run(self, ctx: ScanContext, target: ScanTarget) -> ArtifactResult:
        if target.path is None:
            return ArtifactResult(
                artifact=self.artifact,
                target=target.name,
                outcome=Outcome.SKIPPED,
                error="no local path for this target",
            )

        warnings: list[str] = []
        injected = self._registry is not None
        registry = self._registry or RegistryClient(
            enabled=ctx.config.privacy.enrich_dependencies,
            timeout=ctx.config.registry_timeout_seconds,
        )
        walk = Walk(registry=registry, warn=warnings.append)
        try:
            entries = walk.run(target.path, ctx.config.exclude)
        except Exception as exc:  # noqa: BLE001 — never take the scan down
            ctx.log.exception("dependency walk failed on %s", target.name)
            return ArtifactResult(
                artifact=self.artifact,
                target=target.name,
                outcome=Outcome.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            if not injected:
                # A registry the caller handed us is theirs to close.
                registry.close()

        for message in warnings:
            ctx.log.warning("%s: %s", target.name, message)

        if not entries:
            # No manifests, or none we handle. Distinguishable from a project
            # that genuinely has no dependencies only by the reason (`F18`).
            return ArtifactResult(
                artifact=self.artifact,
                target=target.name,
                outcome=Outcome.SKIPPED,
                error="no dependency manifests found",
            )

        return ArtifactResult(
            artifact=self.artifact,
            target=target.name,
            outcome=Outcome.OK,
            data=[entry.payload() for entry in entries],
        )
