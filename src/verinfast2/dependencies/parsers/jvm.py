"""Java: Maven ``pom.xml``.

Parsed with :mod:`defusedxml` — a pom is untrusted input from the scanned
repository, and ``xml.etree`` is vulnerable to entity-expansion attacks
(`S13`). v1 called ``defusedxml.defuse_stdlib()`` once in ``walk.py``, which
patches the stdlib globally for the whole process — a library must not do
that to its host (`D30`, `L2`).

Version text may be a property reference (``${mavenVersion}``). v1 emitted it
verbatim as ``==${mavenVersion}``. Properties declared in the same pom are
resolved here; one inherited from a parent pom stays unresolved and the
specifier is omitted rather than sent as a literal ``${...}``.
"""

from __future__ import annotations

import re

from verinfast2.dependencies.models import Entry

SOURCE = "maven"

_PROPERTY = re.compile(r"^\$\{([^}]+)\}$")

#: Maven namespaces every element, so a bare "dependencies/dependency" path
#: never matches a real pom. v1's did not match either — its Maven walker
#: silently found nothing on any namespaced pom, which is most of them.
_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def _text(node) -> str | None:
    return node.text.strip() if node is not None and node.text else None


def parse(text: str, path: str) -> list[Entry]:
    from defusedxml.ElementTree import fromstring

    try:
        root = fromstring(text)
    except Exception:
        return []

    properties: dict[str, str] = {}
    for holder in root.findall("properties") + root.findall("m:properties", _NS):
        for child in holder:
            name = child.tag.split("}")[-1]
            if child.text:
                properties[name] = child.text.strip()

    found = root.findall(".//dependencies/dependency") + root.findall(
        ".//m:dependencies/m:dependency", _NS
    )

    entries: list[Entry] = []
    for dependency in found:
        group = _text(dependency.find("groupId")) or _text(
            dependency.find("m:groupId", _NS)
        )
        artifact = _text(dependency.find("artifactId")) or _text(
            dependency.find("m:artifactId", _NS)
        )
        version = _text(dependency.find("version")) or _text(
            dependency.find("m:version", _NS)
        )
        if not group or not artifact:
            continue

        match = _PROPERTY.match(version or "")
        if match:
            version = properties.get(match.group(1))

        entries.append(
            Entry(
                name=f"{group}/{artifact}",
                source=SOURCE,
                specifier=f"=={version}" if version else None,
            )
        )
    return entries
