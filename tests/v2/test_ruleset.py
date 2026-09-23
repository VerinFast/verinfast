"""The shipped ruleset: integrity, provenance, licensing, deduplication.

These guard a generated tree. `scripts/sync_rules.py` writes it; nothing
here should ever be fixed by editing `src/verinfast2/rules/` directly.
"""

import json

import pytest
import yaml

from verinfast2.scanners.ruleset import (
    MANIFEST,
    RULES_DIR,
    engine_command,
    engine_env,
    load_ruleset,
)

RULE_FILES = sorted(p for p in RULES_DIR.rglob("*.y*ml"))


def _rules(path):
    doc = yaml.safe_load(path.read_text(errors="replace"))
    return (doc or {}).get("rules") or []


def test_ruleset_is_present():
    assert MANIFEST.exists(), "run `python scripts/sync_rules.py`"
    assert RULE_FILES, "no rule files shipped"


def test_manifest_matches_the_tree():
    data = json.loads(MANIFEST.read_text())
    assert data["total_files"] == len(RULE_FILES)
    counted = sum(len(_rules(p)) for p in RULE_FILES)
    assert data["total_rules"] == counted


def test_every_source_records_provenance_and_a_licence():
    """S18/S16: a finding set has to be attributable to a rule revision."""
    for source in json.loads(MANIFEST.read_text())["sources"]:
        assert source["license"] == "MIT", source
        assert len(source["revision"]) == 40, "pin a commit, never a branch"
        assert source["url"].startswith("https://")
        assert (RULES_DIR / "LICENSES" / f"{source['name']}.LICENSE").exists()


def test_rule_ids_are_unique():
    """A duplicate id is fatal to the engine, not cosmetic."""
    seen = {}
    for path in RULE_FILES:
        for rule in _rules(path):
            rid = rule.get("id")
            assert rid, f"{path}: rule with no id"
            assert rid not in seen, f"duplicate id {rid}: {path} and {seen[rid]}"
            seen[rid] = path


def test_no_duplicate_rule_bodies():
    """The same logic under two names doubles every finding."""
    import hashlib

    bodies = {}
    for path in RULE_FILES:
        for rule in _rules(path):
            core = {
                k: v for k, v in rule.items() if k not in ("id", "message", "metadata")
            }
            digest = hashlib.sha256(
                yaml.safe_dump(core, sort_keys=True).encode()
            ).hexdigest()
            assert digest not in bodies, f"{rule['id']} duplicates {bodies[digest]}"
            bodies[digest] = rule["id"]


def test_no_test_fixtures_or_sample_code_shipped():
    """Both upstreams keep deliberately-vulnerable samples beside the rules."""
    for path in RULE_FILES:
        rel = str(path.relative_to(RULES_DIR)).lower()
        assert ".test." not in rel, rel
        assert not any(
            part in rel.split("/") for part in ("tests", "test", "testdata")
        ), rel


def test_every_shipped_file_is_a_ruleset():
    for path in RULE_FILES:
        doc = yaml.safe_load(path.read_text(errors="replace"))
        assert isinstance(doc, dict) and "rules" in doc, f"{path} is not a ruleset"


def test_the_join_rule_kept_its_on_key():
    """Regression: YAML 1.1 parses a bare `on` as the boolean True.

    An earlier sync script round-tripped these files through PyYAML, which
    rewrote the join rule's `on:` condition as `true:`. The engine reads
    `on` as a string, saw no conditions, and crashed. Files are copied
    verbatim now; this proves it stayed that way.
    """
    joins = [p for p in RULE_FILES if "mode: join" in p.read_text(errors="replace")]
    if not joins:
        pytest.skip("no join-mode rules in the current corpus")
    for path in joins:
        text = path.read_text(errors="replace")
        assert (
            "\n      on:" in text or "\n        on:" in text
        ), f"{path}: lost its `on:` key"
        assert "true:" not in text, f"{path}: `on:` was rewritten as a boolean"


def test_engine_command_never_uses_config_auto():
    """The licensing and reproducibility requirement, as a test."""
    rs = load_ruleset()
    argv = engine_command(RULES_DIR, MANIFEST.parent / "out.json", rs)
    assert "auto" not in argv
    assert "--config" in argv
    assert str(rs.path) in argv


def test_engine_command_applies_the_exclusions():
    from verinfast2.scanners.ruleset import Ruleset

    rs = Ruleset(path=RULES_DIR, rule_count=2, exclude=("a", "b"), sources=())
    argv = engine_command(RULES_DIR, MANIFEST.parent / "o.json", rs)
    assert argv.count("--exclude-rule") == 2
    assert "a" in argv and "b" in argv


def test_engine_env_forces_utf8():
    """Opengrep's bundled interpreter dies on an ASCII locale."""
    env = engine_env({})
    assert env["PYTHONUTF8"] == "1"
    assert env["LANG"].endswith("UTF-8")
    assert env["LC_ALL"].endswith("UTF-8")


def test_provenance_is_recordable():
    p = load_ruleset().provenance
    assert p["engine"] == "opengrep"
    assert p["rule_count"] > 0
    assert p["sources"] and all("revision" in s for s in p["sources"])
