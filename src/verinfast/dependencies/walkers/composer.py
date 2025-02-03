import json
import os
from pathlib import Path
from typing import List

from verinfast.dependencies.walkers.classes import Walker, Entry
from verinfast.utils.utils import std_exec


class ComposerWalker(Walker):
    dependency_tree = {}

    def initialize(self, root_path: str = "./"):
        root_path = str(Path(root_path).absolute())
        self.install_points: List[Path] = []
        for p in Path(root_path).rglob("**/*.*"):
            if p.name in self.manifest_files:
                self.install_points.append(p)
        for p in self.install_points:
            target_dir = Path(p).parent
            os.chdir(target_dir)
            try:
                res = std_exec(["composer", "install", "--no-dev", "--no-progress"])
                self.log(tag="", msg=res, timestamp=False)
            except Exception as error:
                self.log(tag="ERROR", msg=f"Error with composer install: {error}")
            finally:
                self.walk("./")
            for dep in self.dependency_tree:
                dependency = self.dependency_tree[dep]
                for v in dependency:
                    version = dependency[v]
                    self.entries.append(version)
            os.chdir(root_path)

    def parse(self, file: str, expand=False):
        try:
            with open(file) as f:
                cjson = json.load(f)
                if "license" in cjson and self.dependency_tree.get(cjson["name"]):
                    for version in self.dependency_tree[cjson["name"]]:
                        self.dependency_tree[cjson["name"]][version].license = cjson[
                            "license"
                        ]
                        if "description" in cjson:
                            self.dependency_tree[cjson["name"]][version].summary = (
                                cjson["description"]
                            )
                if "require" in cjson:
                    for k, v in cjson["require"].items():
                        if self.dependency_tree.get(k):
                            self.dependency_tree[k] = self.dependency_tree[k]
                        else:
                            self.dependency_tree[k] = {}
                        if self.dependency_tree[k].get(v):
                            self.dependency_tree[k][v] = self.dependency_tree[k][v]
                        else:
                            self.dependency_tree[k][v] = Entry(
                                name=k, source="composer", specifier=v
                            )
                self.log(self.dependency_tree)
        except Exception as error:
            self.log(f"error parsing {file}")
            try:
                self.log(json.load(file)["name"])
                self.log(json.load(file)["require"])
            except Exception as ex:
                raise ex
            self.log(error)
