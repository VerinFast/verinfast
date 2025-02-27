from pathlib import Path
import json
import platform
import os
import re

from .git_utils import GitUtils
from .repo_handlers import RepoHandlers
from .scanners import ScannerTools
from .file_utils import FileUtils

uname = platform.uname()
system = uname.system
machine = uname.machine


class RepositoryScanner(GitUtils, RepoHandlers, ScannerTools, FileUtils):
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config
        self.log = agent.log
        self.cache = agent.cache
        self.curr_dir = os.getcwd()
        self.temp_dir = Path(os.path.expanduser("~/.verinfast/")).joinpath("temp_repo")
        self.template_definition = agent.template_definition

    def _update_template_definition(self, key, value):
        """Helper method to update template definition"""
        self.template_definition[key] = value

    def scanRepos(self, config=None):
        """Scan all configured repositories"""
        # Need to reset config if it has changed
        if config:
            self.config = config
        self._scan_remote_repos()
        self._scan_local_repos()
        self.log(msg="", tag="Finished repo scans")

    def _parse_repo(self, path, repo_name, branch=None):
        """Scan a single repository"""
        if not self.config.dry:
            os.chdir(path)

        if branch is None:
            branch = "main"

        if self.config.runGit:
            self._initialize_git(path, branch)

        git_output_file = os.path.join(
            self.config.output_dir, f"{repo_name}.git.log.json"
        )
        self.log(
            msg=repo_name, tag="Gathering source code statistics for", display=True
        )

        git_results = self._process_git_log(branch)

        if not self.config.dry:
            with open(git_output_file, "w") as f:
                f.write(json.dumps(git_results, indent=4))
            self.template_definition["gitlog"] = git_results

        self.agent.upload(file=git_output_file, route="git", source=repo_name)

        self._run_file_size_scan(path, repo_name)

        # Run configured scans
        if self.config.runStats:
            self._run_stats_scan(path, repo_name)

        if self.config.runScan:
            self._run_semgrep_scan(repo_name)

        if self.config.runDependencies:
            self._scan_dependencies(repo_name)

        expected_files = {
            "git.log.json": "git",
            "sizes.json": "sizes",
            "stats.json": "stats",
            "findings.json": "findings",
            "dependencies.json": "dependencies",
        }

        # Attempt to upload each file (this will log "File does not exist" in dry mode)
        for file_suffix, route in expected_files.items():
            file_path = os.path.join(
                self.agent.config.output_dir, f"{repo_name}.{file_suffix}"
            )
            self.agent.upload(file=file_path, route=route, source=repo_name)

    def _run_file_size_scan(self, path, repo_name):
        """Run file size analysis"""
        sizes_output_file = os.path.join(
            self.agent.config.output_dir, f"{repo_name}.sizes.json"
        )

        if not self.config.dry:
            self.log(msg=repo_name, tag="Gathering file sizes for", display=True)

            # Using inherited FileUtils methods
            repo_size = self.get_raw_size(".")
            git_size = self.get_raw_size("./.git")
            real_size = repo_size - git_size

            self.log(msg=repo_size, tag="Repo Size")
            self.log(msg=git_size, tag="Git Size")

            sizes = {
                "files": {
                    ".": {"size": repo_size, "loc": 0, "ext": None, "directory": True}
                },
                "metadata": {
                    "env": machine,
                    "real_size": real_size,
                    "uname": system,
                    "branch": self.branch if self.branch else "",
                },
            }

            # Get list of files using FileUtils method
            filelist = self._get_file_list(path)

            # Process files for sizes if needed
            if self.config.shouldManualFileScan:
                for file_info in filelist:
                    fp = file_info["path"]
                    name = file_info["name"]
                    extRe = re.search(r"^[^\.]*\.(.*)", name)
                    ext = extRe.group(1) if extRe else ""

                    sizes["files"][fp] = {
                        "size": os.path.getsize(fp),
                        "loc": self.getloc(fp),
                        "ext": ext,
                        "directory": False,
                    }

            with open(sizes_output_file, "w") as f:
                f.write(json.dumps(sizes, indent=4))

            self._update_template_definition(
                "current_dir_size", sizes["files"].pop(".")
            )
            self._update_template_definition("sizes", sizes)
            self._update_template_definition("filelist", filelist)

        self.agent.upload(file=sizes_output_file, route="sizes", source=repo_name)
