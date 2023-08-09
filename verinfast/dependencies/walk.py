from curses.ascii import isdigit
import json
import os
from pathlib import Path

from requirementstxt import parseFile
from johnnydep.walkers.maven import mavenWalker
from johnnydep.walkers.npm import nodeWalker
from johnnydep.walkers.classes import Entry



# should probably move this to a conf
# Manifests we support
python_matches = ["requirements.txt", "requirements-dev.txt"]
node_matches = ["package.json"]

# TODO: Gemfile parse
# Example: https://github.com/mastodon/mastodon/blob/main/Gemfile
ruby_matches = ["Gemfile"]

# TODO: Parse Cargo.toml
# Example: https://github.com/servo/servo/blob/master/components/style/Cargo.toml
rust_matches = ["Cargo.toml"]

# install commands
node_install = "npm install"

node_install_points = []
pip_files = []

# Finds all manifests we can process in the repo 
# and stores their path in memory
def walk(path:str="./"):
    entries=[]
    mavenWalker.walk(path)
    entries += mavenWalker.entries
    
    for p in Path(path).rglob('**/*.*'):
        if p in python_matches:
            pip_files.append(p)
        if p in node_matches:
            node_install_points.append(p)
    
    for i in node_install_points:
        p = parse_node_install_point(i)
        nodeWalker.walk(p)
    entries+= nodeWalker.entries

# parse node dependency manifests
def parse_node_install_point(path:str):
    target_dir = Path(path).parent
    os.chdir(target_dir)
    os.system(node_install)
    return target_dir
    # return node_license_walk(path)

# parse python dependency manifests
def parse_pip_install_point(path:str):
    temp=parseFile(filename=path, ret=True)
    for l in temp:
        l["source"]="pip"
    return temp

# Walks an installed Node package
def node_license_walk(path:str="./node_modules/"):
    license = {}
    res = []
    for p in Path(path).rglob('**/package.json'):
        with open(p) as file:
            entry = {}
            try:
                d=json.load(file)
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
                
            except:
                pass
            res.append(entry)
    print(json.dumps(res, indent=4))
    return res
