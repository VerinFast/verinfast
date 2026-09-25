"""PHP: ``composer.json``.

v1 ran ``composer install`` and then walked the vendor tree, building a
nested ``dependency_tree`` dict on the *class* rather than the instance — so
two scans in one process shared it (`D5`). The ``require`` map is what the
project declares, and reading it needs no install.
"""

from __future__ import annotations

import json

from verinfast2.dependencies.models import Entry

SOURCE = "composer"


def parse(text: str, path: str) -> list[Entry]:
    try:
        document = json.loads(text)
    except ValueError:
        return []
    if not isinstance(document, dict):
        return []

    entries: list[Entry] = []
    for section in ("require", "require-dev"):
        declared = document.get(section)
        if not isinstance(declared, dict):
            continue
        for name, spec in declared.items():
            # "php" and "ext-*" are platform requirements, not packages.
            if name == "php" or name.startswith("ext-") or name.startswith("lib-"):
                continue
            entries.append(
                Entry(
                    name=name,
                    source=SOURCE,
                    specifier=spec if isinstance(spec, str) else None,
                )
            )
    return entries
