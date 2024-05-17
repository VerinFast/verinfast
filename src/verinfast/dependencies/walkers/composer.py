import json
import os
import subprocess
from pathlib import Path
from typing import List

from verinfast.dependencies.walkers.classes import Walker, Entry


class ComposerWalker(Walker):
    dependency_tree = {}

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
                    "composer install --no-dev --no-progress",
                    capture_output=True,
                    shell=True
                )
            except Exception as error:
                self.log(f'Error with composer install: {error}')
            else:
                self.walk('./')
            os.chdir(root_path)

    def parse(self, file: str, expand=False):
        try:
            with open(file) as f:
                cjson = json.load(f)
                if (
                    "license" in cjson and
                    self.dependency_tree.get(cjson['name'])
                ):
                    for version in self.dependency_tree[cjson['name']]:
                        self.dependency_tree[cjson['name']
                                             ][version].license = cjson[
                                                 'license']
                        if "description" in cjson:
                            self.dependency_tree[cjson['name']
                                                 ][version].summary = cjson[
                                                     'description']
                if 'require' in cjson:
                    for k, v in cjson['require'].items():
                        if self.dependency_tree.get(k):
                            self.dependency_tree[k] = self.dependency_tree[k]
                        else:
                            self.dependency_tree[k] = {}
                        if self.dependency_tree[k].get(v):
                            self.dependency_tree[k][v] = \
                                self.dependency_tree[k][v]
                        else:
                            self.dependency_tree[k][v] = Entry(
                                name=k, source="composer", specifier=v)
                print(self.dependency_tree)
        except Exception as error:
            self.log(f"error parsing {file}")
            try:
                self.log(json.load(file)['name'])
                self.log(json.load(file)['require'])
            except Exception as ex:
                raise ex
            self.log(error)
