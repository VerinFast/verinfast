from curses.ascii import isdigit
import json
import os
import subprocess
from pathlib import Path
from typing import List, TextIO
import xml

import httpx


class Entry(dict):
    def __init__(self,
        name:str,
        source:str,
        specifier:str,
        license,
        requires,
        required_by,
        summary:str
    )->None:
        if not name:
            raise Exception("Entries must have a package name")
        if not source:
            raise Exception("Entries must have a package source")
        
        self.name=name
        self.source=source
        self.specifier=specifier
        self.license=license
        self.requires=requires
        self.required_by=required_by
        self.summary=summary

class Walker():
    def __init__(self, 
        manifest_type:str, #"json", 
        manifest_files:List[str] #["package.json"]
        ) -> None:
        self.files=[]
        self.manifest_files=manifest_files
        self.manifest_type=manifest_type
        self.entries = []
        self.requestx = httpx.Client(http2=True,timeout=None)

    def initialize(self, command:str):
        if command:
            subprocess.call(args=command)

    def getUrl(self, url:str, headers:dict={}):
        return self.requestx.get(url=url, headers=headers)

    def walk(self, path:str="./", parse:bool=True, expand:bool=False):
        print("path in walk")
        print(path)
        print(Path(path).rglob('**/*.*'))
        foo = Path(path).rglob('**/*.*')
        print(dir(foo))
        for p in Path(path).rglob('**/*.*'):
            print("p.name")
            print(p.name)
            print("self.manifest_files")
            print(self.manifest_files)
            if p.name in self.manifest_files:
                self.files.append(p)
                print("Miller time")
                print(p)
                if parse:
                    self.parse(file=str(p.absolute()), expand=expand)
                    print(p)
        
    def parse(self, file, expand=False):
        raise Exception("No parser for this Walker")

    def expand(self, file):
        raise Exception("No expansion for this Walker")
    