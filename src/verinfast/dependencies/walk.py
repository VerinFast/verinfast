import json
from pathlib import Path
from typing import List

import defusedxml

from verinfast.dependencies.walkers.composer import ComposerWalker
from verinfast.dependencies.walkers.maven import MavenWalker
from verinfast.dependencies.walkers.npm import NodeWalker
from verinfast.dependencies.walkers.package_lock import PackageWalker
from verinfast.dependencies.walkers.gemwalker import GemWalker
from verinfast.dependencies.walkers.nuget import NuGetWalker, c_sharp_matches
from verinfast.dependencies.walkers.dockerwalker import DockerWalker
from verinfast.dependencies.walkers.python import PyWalker
from verinfast.dependencies.walkers.go import GoWalker
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


def write_file(output_file: str, entries):
    with open(output_file, 'w') as outfile:
        dicts = [entry.to_json() for entry in entries]
        outfile.write(json.dumps(dicts, indent=4))


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
        manifest_files=[
            "requirements.txt",
            "requirements-dev.txt",
            "pyproject.toml",
            "poetry.lock"
        ],
        manifest_type="txt",
        logger=logger,
        root_dir=path
    )
    gem_walker = GemWalker(
        manifest_files=["gemfile", "Gemfile"],
        manifest_type="ruby",
        logger=logger,
        root_dir=path
    )
    docker_walker = DockerWalker(
        manifest_files=["Dockerfile", "dockerfile", "docker-compose.yml"],
        manifest_type="Dockerfile",
        logger=logger,
        root_dir=path
    )
    composer_walker = ComposerWalker(
        manifest_files=['composer.json'],
        manifest_type='json',
        logger=logger,
        root_dir=path
    )
    go_walker = GoWalker(
        manifest_type="sum",
        manifest_files=["go.sum"],
        logger=logger,
        root_dir=path
    )
    path = str(Path(path).absolute())
    entries: List[Entry] = []
    composer_walker.initialize(root_path=path)
    entries += composer_walker.entries
    mavenWalker.walk(path=path)
    logger(msg="Dependency Scan 10%", display=True)
    entries += mavenWalker.entries
    write_file(output_file=output_file, entries=entries)
    nodeWalker.initialize(root_path=path)
    logger(msg="Dependency Scan 25%", display=True)
    if nodeWalker.entries:
        entries += nodeWalker.entries
    else:
        packageWalker = PackageWalker(
            manifest_type='json',
            logger=logger,
            root_dir=path,
            manifest_files=["package-lock.json"]
        )
        packageWalker.walk(path=path)
        entries += packageWalker.entries
    write_file(output_file=output_file, entries=entries)
    nugetWalker.initialize()
    logger(msg="Dependency Scan 40%", display=True)
    nugetWalker.walk(path=path)
    entries += nugetWalker.entries
    write_file(output_file=output_file, entries=entries)
    py_walker.walk(path=path)
    logger(msg="Dependency Scan 60%", display=True)
    entries += py_walker.entries
    write_file(output_file=output_file, entries=entries)
    gem_walker.walk(path=path)
    logger(msg="Dependency Scan 80%", display=True)
    entries += gem_walker.entries
    write_file(output_file=output_file, entries=entries)
    logger(msg="Dependency Scan 95%", display=True)
    docker_walker.walk(path=path, expand=False)
    entries += docker_walker.entries
    write_file(output_file=output_file, entries=entries)
    logger(msg="Dependency Scan 100%", display=True)
    go_walker.walk(path=path)
    entries += go_walker.entries
    write_file(output_file=output_file, entries=entries)
    return output_file
