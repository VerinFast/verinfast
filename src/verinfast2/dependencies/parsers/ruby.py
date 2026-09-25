"""Ruby: ``Gemfile`` and ``Gemfile.lock``.

v1 shelled out to ``gem install -r --explain`` through ``shell=True`` with
the file path interpolated into the string (`S11`), and then parsed the
explain output by finding the **last hyphen** in each line to split name from
version — which mangles every gem whose name contains one, such as
``rspec-core``. It then also ran ``gemfileparser`` over the same file.

``Gemfile.lock`` is the resolved set and needs neither. When only a
``Gemfile`` is present the declared gems are read directly; that is a range,
not a resolution, and the specifier says so.
"""

from __future__ import annotations

import re

from verinfast2.dependencies.models import Entry

SOURCE = "gem"

#: ``gem "rails", "~> 7.0", require: false`` — name first, then any version
#: constraints, then keyword options we do not want.
_GEM = re.compile(
    r"""^\s*gem\s+['"](?P<name>[^'"]+)['"](?P<rest>.*)$""",
)
_VERSIONS = re.compile(r"""['"]([<>=~!\s\d.]+)['"]""")

#: In a Gemfile.lock's GEM/specs block, a dependency is indented four spaces
#: and its own dependencies six — so indentation is what distinguishes them.
_LOCK_SPEC = re.compile(r"^    (?P<name>\S+) \((?P<version>[^)]+)\)\s*$")


def parse_gemfile(text: str, path: str) -> list[Entry]:
    entries: list[Entry] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0]
        match = _GEM.match(line)
        if not match:
            continue
        # Only the quoted strings before the first keyword option are
        # version constraints; `require: false` and friends are not.
        rest = match.group("rest").split(":")[0]
        versions = [v.strip() for v in _VERSIONS.findall(rest) if v.strip()]
        entries.append(
            Entry(
                name=match.group("name"),
                source=SOURCE,
                specifier=", ".join(versions) or None,
            )
        )
    return entries


def parse_gemfile_lock(text: str, path: str) -> list[Entry]:
    """The resolved gem set, from the ``specs:`` block."""
    entries: list[Entry] = []
    seen: set[str] = set()
    in_specs = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "specs:":
            in_specs = True
            continue
        if in_specs and stripped and not raw.startswith(" "):
            in_specs = False
            continue
        if not in_specs:
            continue
        match = _LOCK_SPEC.match(raw)
        if not match:
            continue
        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)
        entries.append(
            Entry(name=name, source=SOURCE, specifier=f"=={match.group('version')}")
        )
    return entries
