import json
import os
from pathlib import Path
from typing import List

from curses.ascii import isdigit

from dependencies.walkers.classes import Walker, Entry
from typing import TextIO

class NodeWalker(Walker):
    def initialize(self, root_path: str="./"):
        self.install_points:List[Path] = []
        for p in Path(root_path).rglob('**/*.*'):
            if p.name in self.manifest_files:
                self.install_points.append(p)
        for p in self.install_points:
            target_dir = Path(p).parent
            os.chdir(target_dir)
            os.system("npm install")
            print("npm target_dir")
            print(target_dir)
            self.walk('node_modules')

    def parse(self, file:str, expand=False):
        entry = {}
        license={}
        print('NPM parsing file')
        print(file)
        try:
            with open(file) as f:
                d=json.load(f)
                key=d["name"] + "@" + d["version"]
                entry["source"] = "npm"
                entry["name"] = d["name"]
                entry["specifier"] = "==" + d["version"]
                if "license" in d  and type(d["license"]) == type({}):
                    license[key]=d["license"]["type"]
                elif "license" in d:
                    license[key]=d["license"]
                else:
                    license[key]=""
                entry["license"] = license[key]
                entry["requires"] = []
                if "dependencies" in d:
                    for key in d["dependencies"].keys():
                        k = key
                        print(k)
                        value = d["dependencies"][k]
                        print(value)
                        if isdigit(value[0]):
                            value="=="+value
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
            print("An exception occurred in npm.py:", error)
            pass

nodeWalker = NodeWalker(manifest_type='json', manifest_files=["package.json"])
