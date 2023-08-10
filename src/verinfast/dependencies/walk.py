import json
import os
from pathlib import Path
from typing import List

import defusedxml

from verinfast.dependencies.walkers.maven import mavenWalker
from verinfast.dependencies.walkers.npm import nodeWalker
from verinfast.dependencies.walkers.nuget import nugetWalker
from verinfast.dependencies.walkers.classes import Entry

defusedxml.defuse_stdlib()

# Manifests we support
# should probably move this to a conf

# TODO: Pip parse
python_matches = ["requirements.txt", "requirements-dev.txt"]

# TODO: Gemfile parse
# Example: https://github.com/mastodon/mastodon/blob/main/Gemfile
ruby_matches = ["Gemfile"]

# TODO: Parse Cargo.toml
# Example: https://github.com/servo/servo/blob/master/components/style/Cargo.toml
rust_matches = ["Cargo.toml"]

# Finds all manifests we can process in the repo 
# and stores their path in memory
def walk(path:str="./", output_file="./dependencies.json"):
    path = str(Path(path).absolute())
    entries:List[Entry]=[]
    mavenWalker.walk(path=path)
    entries += mavenWalker.entries
    nodeWalker.initialize(root_path=path)
    entries += nodeWalker.entries
    nugetWalker.initialize()
    nugetWalker.walk(path=path)
    entries += nugetWalker.entries

    with open(output_file, 'w') as outfile:
        dicts = [entry.to_json() for entry in entries]
        outfile.write(json.dumps(dicts, indent=4))
    return output_file
