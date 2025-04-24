import glob
import json
import subprocess
from pathlib import Path
from typing import List
import httpx
import os


class Entry(dict):
    def __init__(
        self,
        name: str,
        source: str,
        specifier: str = None,
        license: str = None,
        summary: str = None,
        requires=None,
        required_by=None,
    ) -> None:
        if not name:
            raise Exception("Entries must have a package name")
        if not source:
            raise Exception("Entries must have a package source")

        self.name = name
        self.source = source
        self.specifier = specifier
        self.license = license
        self.requires = requires
        self.required_by = required_by
        self.summary = summary

    def __str__(self) -> str:
        d = self.to_json()
        return json.dumps(d, indent=4)

    def __repr__(self) -> str:
        return str(self)

    def to_json(self) -> dict:
        d = {}
        d["name"] = self.name
        d["source"] = self.source
        if self.specifier:
            d["specifier"] = self.specifier
        if self.license:
            d["license"] = self.license
        if self.summary:
            d["summary"] = self.summary
        if self.required_by:
            d["required_by"] = self.required_by
        return d


class Walker:
    def __init__(
        self,
        manifest_type: str,  # "json",
        manifest_files: List[str],  # ["package.json"]
        logger,
        root_dir: str = "./",
        print_name: str = None,
    ) -> None:
        if print_name:
            logger(print_name)
        self.files = []
        new_files = []
        for f in manifest_files:
            if "*" in f:
                full_paths = glob.glob(os.path.join(root_dir, f))
                expanded = [os.path.basename(p) for p in full_paths]
                new_files.extend(expanded)
            else:
                new_files.append(f)
        self.manifest_files = new_files.copy()
        self.manifest_type = manifest_type
        self.entries = []
        self.requestx = httpx.Client(http2=True, timeout=None)
        self.loggerFunc = logger

    def initialize(self, command: str):
        if command:
            subprocess.call(args=command)

    def log(self, msg, tag=None, display=False, timestamp=True):
        self.loggerFunc(msg, tag=tag, display=display, timestamp=timestamp)

    def getUrl(self, url: str, headers: dict = {}):
        try:
            return self.requestx.get(url=url, headers=headers).content.decode(
                "utf-8-sig"
            )
        except Exception as e:
            self.loggerFunc(f"Failed to get URL: {url}, {e}", display=False)
            return None

    def walk(
        self, path: str = "./", parse: bool = True, expand: bool = False, debug: int = 0
    ):
        for p in Path(path).rglob("**/*"):
            if debug > 1:
                self.log(f"EVALUATING: {p}", display=(debug > 2))
            if p.name in self.manifest_files:
                if debug > 0:
                    self.log(f"FOUND: {p.name}", display=True)
                self.files.append(p)
                if parse:
                    self.parse(file=str(p.absolute()), expand=expand)

    def parse(self, file: str, expand=False):
        raise Exception("No parser for this Walker")

    def expand(self, file):
        raise Exception("No expansion for this Walker")
