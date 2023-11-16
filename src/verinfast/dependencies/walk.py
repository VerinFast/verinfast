import json
from pathlib import Path
from typing import List

import defusedxml

from verinfast.dependencies.walkers.maven import MavenWalker
from verinfast.dependencies.walkers.npm import NodeWalker
from verinfast.dependencies.walkers.nuget import NuGetWalker, c_sharp_matches
from verinfast.dependencies.walkers.python import PyWalker
from verinfast.dependencies.walkers.classes import Entry

defusedxml.defuse_stdlib()

# Manifests we support
# should probably move this to a conf

# TODO: Gemfile parse
# Example: https://github.com/mastodon/mastodon/blob/main/Gemfile
ruby_matches = ["Gemfile"]

# TODO: Parse Cargo.toml
# Example: https://github.com/servo/servo/blob/master/components/style/Cargo.toml # noqa: E501
rust_matches = ["Cargo.toml"]


# Finds all manifests we can process in the repo
# and stores their path in memory
def walk(logger, path: str = "./", output_file="./dependencies.json"):
    mavenWalker = MavenWalker(
        manifest_type="xml",
        manifest_files=["pom.xml"],
        logger=logger,
        root_dir=path
    )

    nodeWalker = NodeWalker(
        manifest_type='json',
        manifest_files=["package.json"],
        logger=logger,
        root_dir=path
    )

    nugetWalker = NuGetWalker(
        manifest_type='xml',
        manifest_files=c_sharp_matches,
        logger=logger,
        root_dir=path
    )

    py_walker = PyWalker(
        manifest_files=["requirements.txt", "requirements-dev.txt"],
        manifest_type="txt",
        logger=logger,
        root_dir=path
    )

    path = str(Path(path).absolute())
    entries: List[Entry] = []
    mavenWalker.walk(path=path)
    entries += mavenWalker.entries
    nodeWalker.initialize(root_path=path)
    entries += nodeWalker.entries
    nugetWalker.initialize()
    nugetWalker.walk(path=path)
    entries += nugetWalker.entries
    py_walker.walk(path=path)
    entries += py_walker.entries

    with open(output_file, 'w') as outfile:
        dicts = [entry.to_json() for entry in entries]
        outfile.write(json.dumps(dicts, indent=4))
    return output_file
