import json
import os
from typing import List

from dependencies.walkers.maven import mavenWalker
from dependencies.walkers.npm import nodeWalker
from dependencies.walkers.nuget import nugetWalker
from dependencies.walkers.classes import Entry

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
    entries:List[Entry]=[]
    mavenWalker.walk(path=path)
    entries += mavenWalker.entries
    nodeWalker.initialize(root_path=path)
    entries += nodeWalker.entries
    nugetWalker.initialize()
    nugetWalker.walk(path=path)
    entries += nugetWalker.entries

    with open(output_file, 'w') as outfile:
        outfile.write(json.dumps(entries, indent=4))
    return output_file
