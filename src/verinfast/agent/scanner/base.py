from pathlib import Path
import os

from .git_utils import GitUtils
from .repo_handlers import RepoHandlers
from .scanners import ScannerTools
from .file_utils import FileUtils


class RepositoryScanner(GitUtils, RepoHandlers, ScannerTools, FileUtils):
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config
        self.log = agent.log
        self.cache = agent.cache
        self.curr_dir = os.getcwd()
        self.temp_dir = Path(os.path.expanduser('~/.verinfast/')).joinpath('temp_repo')
        self.template_definition = agent.template_definition

    def _update_template_definition(self, key, value):
        """Helper method to update template definition"""
        self.template_definition[key] = value

    def scanRepos(self):
        """Scan all configured repositories"""
        self._scan_remote_repos()
        self._scan_local_repos()
        self.log(msg='', tag="Finished repo scans")

    def _parse_repo(self, path, repo_name, branch=None):
        """Scan a single repository"""
        if not self.config.dry:
            os.chdir(path)

        if branch is None:
            branch = "main"

        if self.config.runGit:
            self._initialize_git(path, branch)

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
            "dependencies.json": "dependencies"
        }

        # Attempt to upload each file (this will log "File does not exist" in dry mode)
        for file_suffix, route in expected_files.items():
            file_path = os.path.join(
                self.agent.config.output_dir,
                f"{repo_name}.{file_suffix}"
            )
            self.agent.upload(
                file=file_path,
                route=route,
                source=repo_name
            )
