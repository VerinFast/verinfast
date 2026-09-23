""".NET: ``*.csproj`` ``<PackageReference>`` elements.

Licences come from NuGet, which needs two round-trips per package, so they
are fetched by the scanner rather than here — a parser stays pure.
"""

from __future__ import annotations

from verinfast2.dependencies.models import Entry

SOURCE = "nuget"


def parse(text: str, path: str) -> list[Entry]:
    from defusedxml.ElementTree import fromstring

    try:
        root = fromstring(text)
    except Exception:
        return []

    entries: list[Entry] = []
    for reference in root.findall(".//ItemGroup/PackageReference"):
        name = reference.attrib.get("Include")
        if not name:
            continue
        # A version can be an attribute or a child element; v1 read only the
        # attribute and raised a KeyError on the child form.
        version = reference.attrib.get("Version")
        if not version:
            child = reference.find("Version")
            version = child.text.strip() if child is not None and child.text else None
        entries.append(
            Entry(
                name=name,
                source=SOURCE,
                specifier=f"=={version}" if version else None,
            )
        )
    return entries
