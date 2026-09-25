"""Go: ``go.sum``.

Two lines per module — one for the zip, one for the ``go.mod`` — so the
``/go.mod`` suffix is stripped and duplicates collapse.
"""

from __future__ import annotations

from verinfast2.dependencies.models import Entry

SOURCE = "Go"


def parse(text: str, path: str) -> list[Entry]:
    seen: set[tuple[str, str]] = set()
    entries: list[Entry] = []
    for line in text.splitlines():
        parts = line.split()
        # v1 did `name, version, hash = line.split(" ")`, which raises on a
        # blank line or any line with an unexpected field count — and go.sum
        # ends with a newline, so it raised on every file (`D29`).
        if len(parts) < 2:
            continue
        name, version = parts[0], parts[1]
        version = version.removesuffix("/go.mod")
        if (name, version) in seen:
            continue
        seen.add((name, version))
        entries.append(Entry(name=name, source=SOURCE, specifier=version))
    return entries
