import glob
import json
import subprocess
from pathlib import Path
from typing import List

import httpx


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


class Walker():
    def __init__(
        self,
        manifest_type: str,  # "json",
        manifest_files: List[str],  # ["package.json"]
        logger,
        root_dir: str = "./",
        print_name: str = None
    ) -> None:
        if print_name:
            logger(print_name)
        self.files = []
        self.manifest_files = manifest_files.copy()
        for f in self.manifest_files:
            if "*" in f:
                expanded = glob.glob(f, root_dir=root_dir)
                self.manifest_files.remove(f)
                self.manifest_files += expanded
        self.manifest_type = manifest_type
        self.entries = []
        self.requestx = httpx.Client(http2=True, timeout=None)
        self.loggerFunc = logger

    def initialize(self, command: str):
        if command:
            subprocess.call(args=command)

    def log(self, msg, tag=None, display=False, timestamp=True):
        self.loggerFunc(
            msg,
            tag=tag,
            display=display,
            timestamp=timestamp
        )

    def getUrl(self, url: str, headers: dict = {}):
        try:
            return  (  # noqa: E271
                        self
                            .requestx  # NOQA: E131
                            .get(url=url, headers=headers)
                            .content
                            .decode('utf-8-sig')
                    )
        except Exception as e:
            self.loggerFunc(
                f"Failed to get URL: {url}, {e}",
                display=False
            )
            return None

    def walk(self,
             path: str = "./",
             parse: bool = True,
             expand: bool = False,
             debug: int = 0):
        for p in Path(path).rglob('**/*'):
            if debug > 1:
                self.log(F"EVALUATING: {p}", display=(debug > 2))
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
