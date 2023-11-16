import json
import os
import subprocess
from pathlib import Path
from typing import List

from curses.ascii import isdigit

from verinfast.dependencies.walkers.classes import Walker, Entry


class NodeWalker(Walker):
    def initialize(self, root_path: str = "./"):
        root_path = str(Path(root_path).absolute())
        self.install_points: List[Path] = []
        for p in Path(root_path).rglob('**/*.*'):
            if p.name in self.manifest_files:
                self.install_points.append(p)
        for p in self.install_points:
            target_dir = Path(p).parent
            os.chdir(target_dir)
            try:
                subprocess.run(
                    "npm install --production --silent --yes",
                    capture_output=True,
                    shell=True
                )
            except Exception as error:
                self.log(f'Error with npm install: {error}')
            else:
                self.walk('node_modules')
            os.chdir(root_path)

    def parse(self, file: str, expand=False):
        entry = {}
        license = {}
        try:
            with open(file) as f:
                d = json.load(f)
                if "name" in d and "version" in d:
                    key = d["name"] + "@" + d["version"]
                    entry["source"] = "npm"
                    entry["name"] = d["name"]
                    entry["specifier"] = "==" + d["version"]
                    if "license" in d and isinstance(d["license"], dict):
                        license[key] = d["license"]["type"]
                    elif "license" in d and isinstance(d["license"], list):
                        license[key] = ' '.join(d["license"])
                    elif "license" in d:
                        license[key] = d["license"]
                    else:
                        license[key] = ""
                    entry["license"] = license[key]
                    entry["requires"] = []
                    if "dependencies" in d:
                        for key in d["dependencies"].keys():
                            k = key
                            value = d["dependencies"][k]
                            if isdigit(value[0]):
                                value = "==" + value
                            entry["requires"].append(k+value)

                    entry["required_by"] = []
                    if "description" in d:
                        entry["summary"] = d["description"]
                    else:
                        entry["summary"] = ""

                    e = Entry(
                        name=entry["name"],
                        specifier=entry["specifier"],
                        source=entry["source"],
                        license=entry["license"],
                        summary=entry["summary"]
                    )
                    self.entries.append(e)
        except Exception as error:
            # handle the exception
            self.log(f"error parsing {file}")
            self.log(error)
