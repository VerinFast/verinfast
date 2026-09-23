#!/usr/bin/env python3
"""Vendor the security rulesets VerinFast ships, deduplicated.

VerinFast scans with an engine that takes Semgrep-format rules, but it does
**not** use ``--config auto``: those registry rules are licensed for
internal, non-competing, non-SaaS use only, and fetching them at scan time
makes a scan irreproducible. Instead the rules ship with the agent, pinned
to a revision, under licences that permit commercial and hosted use.

This script is the only thing that writes ``src/verinfast2/rules/``. Run it
to add a source, bump a pin, or re-check the deduplication:

    python scripts/sync_rules.py            # rebuild from the pinned revisions
    python scripts/sync_rules.py --check    # verify the tree matches; exit 1 if not
    python scripts/sync_rules.py --update   # move the pins to each source's HEAD

Deduplication happens on two keys, because two sources can collide either
way round:

* **rule id** — the engine itself rejects a duplicate id, so this is fatal
  rather than cosmetic;
* **normalised body** — the rule minus its id, message and metadata. Two
  sources can ship the same logic under different names; keeping both means
  every hit is reported twice.

Earlier sources in :data:`SOURCES` win a collision, and every drop is
recorded in the manifest so the loss is auditable rather than silent.

**Rule files are copied byte for byte and never re-serialised.** An earlier
version of this script parsed each file and dumped it back out, which
silently corrupted ``rules/generic/jsp-likely-xss.yaml``: YAML 1.1 treats a
bare ``on`` as a boolean, so PyYAML read the join rule's ``on:`` condition
key as ``True`` and wrote it back as ``true:``. The engine's parser reads
``on`` as a string, saw a join block with no conditions, and crashed with
``reduce() of empty iterable``. Round-tripping YAML you do not own is a
class of bug, not an instance — so duplicates are expressed as an exclusion
list the scan applies with ``--exclude-rule``, not by rewriting the file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - a dev dependency
    sys.exit("pyyaml is required: pip install '.[dev]'")

REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "src" / "verinfast2" / "rules"
MANIFEST = RULES_DIR / "MANIFEST.json"

#: Keys that name a rule rather than define its behaviour. Excluded from the
#: body hash so the same logic under two names still collides.
IDENTITY_KEYS = frozenset({"id", "message", "metadata"})

#: Licences a source may carry to be vendored here, and a phrase that must
#: appear in its LICENSE text.
#:
#: The whole point of shipping rules is to escape the registry's
#: internal-only, non-competing, non-SaaS terms, so a source that drags a
#: different restriction back in defeats the exercise. Permissive only: no
#: copyleft, no non-commercial clause, no Commons Clause.
ALLOWED_LICENSES: dict[str, str] = {
    "MIT": "Permission is hereby granted, free of charge",
    "Apache-2.0": "Apache License",
    "BSD-3-Clause": "Redistribution and use in source and binary forms",
    "BSD-2-Clause": "Redistribution and use in source and binary forms",
}

#: Phrases that disqualify a licence text whatever it calls itself. Checked
#: after the match above, because "MIT" in the metadata means nothing if the
#: file says something else.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    "NonCommercial",
    "Commons Clause",
    "GNU GENERAL PUBLIC LICENSE",
    "GNU AFFERO",
    "GNU LESSER",
)


def verify_license(source: "Source", text: str) -> None:
    """Check a source's declared licence against the text it ships.

    ``Source.license`` is a string someone typed. This makes it a claim the
    script checks rather than a label it trusts.

    Raises:
        SystemExit: the licence is not on the allowlist, the text does not
            match the declaration, or the text carries a disqualifying term.
    """
    if source.license not in ALLOWED_LICENSES:
        raise SystemExit(
            f"{source.name}: licence {source.license!r} is not on the allowlist "
            f"({', '.join(sorted(ALLOWED_LICENSES))}). Shipping it would reintroduce "
            "the restriction this ruleset exists to escape."
        )
    marker = ALLOWED_LICENSES[source.license]
    if marker.lower() not in text.lower():
        raise SystemExit(
            f"{source.name}: declared {source.license} but its LICENSE file does not "
            f"read like one (expected to find {marker!r})."
        )
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text.lower():
            raise SystemExit(
                f"{source.name}: LICENSE text contains {phrase!r}, which is not "
                f"compatible with shipping it in a commercial hosted product."
            )


@dataclass(frozen=True)
class Source:
    """One upstream ruleset.

    Attributes:
        name: directory name under ``rules/``.
        url: git remote.
        revision: the pinned commit. Never a branch — a scan has to be
            reproducible, and "whatever main said that day" is not.
        license: SPDX identifier. Checked against the shipped LICENSE text
            by :func:`verify_license` — not taken on trust.
    """

    name: str
    url: str
    revision: str
    license: str


#: Order matters: an earlier source wins a duplicate.
SOURCES: tuple[Source, ...] = (
    Source(
        name="elttam",
        url="https://github.com/elttam/semgrep-rules",
        revision="244268562cc92d33f54b8a60a187df5520f91b26",
        license="MIT",
    ),
    Source(
        name="0xdea",
        url="https://github.com/0xdea/semgrep-rules",
        revision="72b78c1ff2f1acfad0c19dc6528e0039b534716a",
        license="MIT",
    ),
)


def is_fixture(path: Path) -> bool:
    """Test fixtures and vulnerable sample code — never shipped.

    Both upstreams keep deliberately-vulnerable samples next to the rules
    that match them. Shipping those would put exploit code in the agent and
    make it scan itself.
    """
    parts = {p.lower() for p in path.parts}
    return (
        ".test." in path.name
        or path.name.endswith((".test.yaml", ".test.yml"))
        or bool(parts & {"tests", "test", "testdata", "fixtures", ".github"})
    )


def rule_documents(path: Path) -> list[dict[str, Any]] | None:
    """The rules in a YAML file, or None if it is not a ruleset."""
    try:
        doc = yaml.safe_load(path.read_text(errors="replace"))
    except yaml.YAMLError:
        return None
    if not isinstance(doc, dict):
        return None
    rules = doc.get("rules")
    if not isinstance(rules, list):
        return None
    return [r for r in rules if isinstance(r, dict) and "id" in r]


def body_digest(rule: dict[str, Any]) -> str:
    """A hash of what the rule *does*, ignoring what it is called."""
    core = {k: v for k, v in rule.items() if k not in IDENTITY_KEYS}
    return hashlib.sha256(
        yaml.safe_dump(core, sort_keys=True, default_flow_style=False).encode()
    ).hexdigest()


@dataclass
class Dropped:
    """A rule the deduplicator removed, and why."""

    rule_id: str
    source: str
    path: str
    reason: str
    kept_from: str


@dataclass
class Build:
    files: dict[str, bytes] = field(default_factory=dict)  # dest path -> raw bytes
    counts: dict[str, int] = field(default_factory=dict)  # source -> rules kept
    dropped: list[Dropped] = field(default_factory=list)
    licenses: dict[str, str] = field(default_factory=dict)  # source -> text


def clone(source: Source, into: Path) -> Path:
    """Check out a source at its pinned revision."""
    dest = into / source.name
    subprocess.run(
        ["git", "clone", "--quiet", source.url, str(dest)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", source.revision],
        check=True,
        capture_output=True,
    )
    return dest


def head_revision(source: Source) -> str:
    out = subprocess.run(
        ["git", "ls-remote", source.url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.split()[0]


def build(checkouts: dict[str, Path]) -> Build:
    """Collect and deduplicate the shipped ruleset.

    Files are read as bytes and written back unchanged. Deduplication is
    recorded, not applied by editing: a duplicate rule id lands in the
    manifest's ``exclude`` list, which the scan passes to the engine as
    ``--exclude-rule``.
    """
    result = Build()
    seen_ids: dict[str, str] = {}  # rule id -> "source:path"
    seen_bodies: dict[str, str] = {}  # body digest -> "source:id"

    for source in SOURCES:
        root = checkouts[source.name]
        kept_rules = 0

        for license_name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
            candidate = root / license_name
            if candidate.exists():
                text = candidate.read_text(errors="replace")
                verify_license(source, text)
                result.licenses[source.name] = text
                break
        else:
            raise SystemExit(f"{source.name}: no LICENSE file; refusing to vendor it")

        for path in sorted(root.rglob("*.y*ml")):
            if ".git" in path.parts or is_fixture(path.relative_to(root)):
                continue
            rules = rule_documents(path)
            if not rules:
                continue

            for rule in rules:
                rid = rule["id"]
                where = f"{source.name}:{path.relative_to(root)}"

                if rid in seen_ids:
                    result.dropped.append(
                        Dropped(
                            rid,
                            source.name,
                            str(path.relative_to(root)),
                            "duplicate rule id",
                            seen_ids[rid],
                        )
                    )
                    continue

                digest = body_digest(rule)
                if digest in seen_bodies:
                    result.dropped.append(
                        Dropped(
                            rid,
                            source.name,
                            str(path.relative_to(root)),
                            "identical rule body",
                            seen_bodies[digest],
                        )
                    )
                    continue

                seen_ids[rid] = where
                seen_bodies[digest] = f"{source.name}:{rid}"
                kept_rules += 1

            # Verbatim. See the module docstring for why this is not a dump.
            result.files[f"{source.name}/{path.relative_to(root)}"] = path.read_bytes()

        result.counts[source.name] = kept_rules

    return result


def manifest(result: Build) -> dict[str, Any]:
    return {
        "_comment": (
            "Generated by scripts/sync_rules.py. Do not edit by hand. "
            "These rules ship with the agent instead of being fetched with "
            "--config auto, which is both a licensing and a reproducibility "
            "requirement."
        ),
        "sources": [
            {
                "name": s.name,
                "url": s.url,
                "revision": s.revision,
                "license": s.license,
                "rules": result.counts.get(s.name, 0),
            }
            for s in SOURCES
        ],
        "total_rules": sum(result.counts.values()),
        "total_files": len(result.files),
        # Passed to the engine as --exclude-rule. Files are copied verbatim,
        # so a duplicate is suppressed at scan time rather than edited out.
        "exclude": sorted({d.rule_id for d in result.dropped}),
        "deduplicated": [
            {
                "id": d.rule_id,
                "source": d.source,
                "path": d.path,
                "reason": d.reason,
                "kept_from": d.kept_from,
            }
            for d in result.dropped
        ],
    }


def write(result: Build) -> None:
    if RULES_DIR.exists():
        for child in RULES_DIR.iterdir():
            if child.name in ("README.md", "CLAUDE.md"):
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    for dest, raw in result.files.items():
        out = RULES_DIR / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)

    licenses = RULES_DIR / "LICENSES"
    licenses.mkdir(exist_ok=True)
    for name, text in result.licenses.items():
        (licenses / f"{name}.LICENSE").write_text(text)

    MANIFEST.write_text(json.dumps(manifest(result), indent=2) + "\n")


def check(result: Build) -> int:
    """Verify the committed tree matches what the pins produce."""
    problems: list[str] = []

    for dest, raw in result.files.items():
        on_disk = RULES_DIR / dest
        if not on_disk.exists():
            problems.append(f"missing: {dest}")
        elif on_disk.read_bytes() != raw:
            problems.append(f"differs: {dest}")

    expected = {RULES_DIR / d for d in result.files}
    for path in RULES_DIR.rglob("*.y*ml"):
        if path not in expected:
            problems.append(f"unexpected: {path.relative_to(RULES_DIR)}")

    if not MANIFEST.exists():
        problems.append("missing: MANIFEST.json")
    elif json.loads(MANIFEST.read_text()) != manifest(result):
        problems.append("differs: MANIFEST.json")

    for problem in problems:
        print(f"  ! {problem}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify, write nothing")
    ap.add_argument("--update", action="store_true", help="move pins to each HEAD")
    args = ap.parse_args()

    if args.update:
        for s in SOURCES:
            print(f"{s.name}: {s.revision} -> {head_revision(s)}")
        print("\nEdit SOURCES in this file with the revisions above, then re-run.")
        return 0

    with tempfile.TemporaryDirectory(prefix="verinfast-rules-") as tmp:
        checkouts = {s.name: clone(s, Path(tmp)) for s in SOURCES}
        result = build(checkouts)

    if args.check:
        rc = check(result)
        print("ruleset matches the pins" if rc == 0 else "ruleset is out of date")
        return rc

    write(result)
    for s in SOURCES:
        print(
            f"  {s.name:8s} {result.counts.get(s.name, 0):4d} rules  ({s.license}, {s.revision[:12]})"
        )
    print(
        f"  {'total':8s} {sum(result.counts.values()):4d} rules in {len(result.files)} files"
    )
    if result.dropped:
        print(f"  deduplicated away: {len(result.dropped)}")
        for d in result.dropped:
            print(f"    - {d.rule_id} ({d.source}) — {d.reason}, kept {d.kept_from}")
    else:
        print("  deduplicated away: 0 (the sources are currently disjoint)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
