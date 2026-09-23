"""Containers: ``Dockerfile`` and ``docker-compose.yml`` base images.

An image address is ``[registry[:port]/]name[:tag|@digest]``, and the colon
in a registry port looks exactly like the colon before a tag — which is why
the split is anchored on the last slash.
"""

from __future__ import annotations

from verinfast2.dependencies.models import Entry

DOCKERFILE_SOURCE = "Dockerfile"
COMPOSE_SOURCE = "docker-compose"


def split_address(address: str) -> tuple[str, str]:
    """``name, specifier`` from an image address. ``*`` when unpinned."""
    name, specifier = address, "*"
    if "@" in name:
        name, _, specifier = name.partition("@")
        return name, specifier or "*"
    if "/" in name:
        head, _, tail = name.rpartition("/")
        if ":" in tail:
            image, _, tag = tail.partition(":")
            return f"{head}/{image}", tag or "*"
        return name, "*"
    if ":" in name:
        name, _, specifier = name.partition(":")
    return name, specifier or "*"


def parse(text: str, path: str) -> list[Entry]:
    entries: list[Entry] = []
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("from "):
            address = line.split(None, 1)[1].strip()
            # `FROM x AS builder` names a stage, not part of the image.
            address = address.split()[0]
            source = DOCKERFILE_SOURCE
        elif lowered.startswith("image:"):
            address = line.partition(":")[2].strip().strip("\"'")
            source = COMPOSE_SOURCE
        else:
            continue
        if not address or address.startswith("$"):
            continue
        name, specifier = split_address(address)
        if not name:
            continue
        entries.append(
            Entry(name=name, source=source, specifier=specifier, required_by=path)
        )
    return entries
