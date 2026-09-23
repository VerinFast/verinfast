"""Locating and invoking the security ruleset VerinFast ships.

VerinFast does **not** use ``--config auto``. Those registry rules are
licensed for internal, non-competing, non-SaaS use only, and fetching them at
scan time makes a scan irreproducible. The rules ship with the agent instead,
vendored by ``scripts/sync_rules.py`` from MIT-licensed sources pinned to a
revision.

The engine is Opengrep — the LGPL-2.1 community fork of Semgrep CE. It is
rule- and output-compatible, so ATD v3's findings ingest is unaffected, and
it is distributed as a binary rather than a PyPI package, which is why the
scanner runs it as a subprocess (`L6`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where ``scripts/sync_rules.py`` writes the vendored rules.
RULES_DIR: Path = Path(__file__).resolve().parent.parent / "rules"
MANIFEST: Path = RULES_DIR / "MANIFEST.json"

#: Engine binary. Opengrep is not on PyPI; it is fetched or vendored as a
#: signed release binary and invoked by name.
ENGINE = "opengrep"


@dataclass(frozen=True)
class Ruleset:
    """The rules a scan will run, and what it took to get them.

    Attributes:
        path: directory to hand the engine as ``--config``.
        rule_count: how many rules the manifest says are shipped.
        exclude: rule ids the deduplicator suppressed. Passed as
            ``--exclude-rule``; empty while the sources stay disjoint.
        sources: provenance — repository, pinned revision and licence for
            each upstream, recorded in the findings artifact so a finding
            set is explainable months later (`S18`).
    """

    path: Path
    rule_count: int
    exclude: tuple[str, ...]
    sources: tuple[dict[str, Any], ...]

    @property
    def provenance(self) -> dict[str, Any]:
        """What to record alongside the findings."""
        return {
            "engine": ENGINE,
            "rule_count": self.rule_count,
            "excluded_rules": list(self.exclude),
            "sources": [
                {k: s[k] for k in ("name", "url", "revision", "license") if k in s}
                for s in self.sources
            ],
        }


def load_ruleset(rules_dir: Path | None = None) -> Ruleset:
    """Read the shipped ruleset's manifest.

    Raises:
        FileNotFoundError: the ruleset is missing. Run
            ``python scripts/sync_rules.py``.
    """
    root = rules_dir or RULES_DIR
    manifest = root / "MANIFEST.json"
    if not manifest.exists():
        raise FileNotFoundError(
            f"no ruleset at {root}; run `python scripts/sync_rules.py`"
        )
    data = json.loads(manifest.read_text())
    return Ruleset(
        path=root,
        rule_count=int(data.get("total_rules", 0)),
        exclude=tuple(data.get("exclude", ())),
        sources=tuple(data.get("sources", ())),
    )


def engine_command(
    target: Path, output: Path, ruleset: Ruleset, *, engine: str = ENGINE
) -> list[str]:
    """The exact argv for one scan.

    No ``--config auto``: the ruleset is a local directory. No network is
    needed or used.
    """
    argv = [
        engine,
        "scan",
        "--config",
        str(ruleset.path),
        "--json",
        f"--json-output={output}",
    ]
    for rule_id in ruleset.exclude:
        argv += ["--exclude-rule", rule_id]
    argv.append(str(target))
    return argv


def engine_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """The environment the engine needs.

    Opengrep bundles its own interpreter, which picks its default encoding
    from the locale. On a container with no ``LANG`` set it falls back to
    ASCII and dies reading any rule containing a non-ASCII byte::

        UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2

    Several shipped rules contain typographic punctuation, so this is not
    hypothetical — it reproduces on a stock slim image. Forcing UTF-8 is
    cheap and removes the whole class.
    """
    env = dict(os.environ if base is None else base)
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")
    env["PYTHONUTF8"] = "1"
    return env
