import json

from curses.ascii import isdigit

from johnnydep.walkers.classes import Walker, Entry
from typing import TextIO

class NodeWalker(Walker):
    def parse(self, path:TextIO):
        entry = {}
        try:
            d=json.load(path)
            key=d["name"] + "@" + d["version"]
            entry["source"] = "npm"
            entry["name"] = d["name"]
            entry["specifier"] = "==" + d["version"]
            if type(d["license"]) == type({}):
                license[key]=d["license"]["type"]
            else:
                license[key]=d["license"]
            entry["license"] = license[key]
            entry["requires"] = []
            for key in d["dependencies"].keys():
                k = key
                value = d["dependencies"]
                if isdigit(value[0]):
                    value="=="+value
                entry["requires"].append(k+value)

            entry["required_by"] = []
            entry["summary"] = d["description"]
            e = Entry(
                name=entry["name"],
                specifier=entry["specifier"],
                source=entry["source"],
                license=entry["license"],
                summary=entry["summary"]
            )
            self.entries.append(e)
        except:
            pass

nodeWalker = NodeWalker(manifest_type='json', manifest_files=["package.json"])
