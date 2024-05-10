import json
import os
import subprocess
from pathlib import Path
from typing import List

from verinfast.dependencies.walkers.classes import Walker, Entry


class ComposerWalker(Walker):
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
                if any([e.name == cjson['name'] for e in self.entries]):
                    existing: Entry = next(entry for entry in self.entries if entry.name == cjson['name'])
                    existing.license = cjson['license']
                    existing.summary = cjson['description']
                if 'require' in cjson:
                    for k, v in cjson['require'].items():
                        if not any([e.name == k for e in self.entries]):
                            e = Entry(
                                name=k,
                                source="composer",
                                specifier=v,
                            )
                            self.entries.append(e)

        except Exception as error:
            self.log(f"error parsing {file}")
            self.log(error)

