import os
import traceback
from pathlib import Path
import re
import shutil

from verinfast.utils.utils import get_repo_name_url_and_branch


class RepoHandlers:
    def _scan_remote_repos(self):
        print(self.config.config, "self.config.config")  # noqa: E501
        if "repos" not in self.config.config:
            self.log(msg="", tag="No remote repos", display=True)
            return

        repos = self.config.config["repos"]
        if not repos:
            self.log(msg="", tag="No remote repos", display=True)
            return

        for repo_url in [r for r in repos if len(r) > 0]:
            repo_info = get_repo_name_url_and_branch(repo_url)
            repo_name = repo_info["repo_name"]
            repo_url = repo_info["repo_url"]
            branch = repo_info["branch"]

            self.log(msg=repo_name, tag="Processing", display=True)
            self.log(msg=repo_url, tag="URL", display=True)
            self.log(msg=branch, tag="Branch Specified", display=True)

            if not self._prepare_temp_directory():
                continue

            if not self.config.dry and self.config.runGit:
                if not self._clone_repository(repo_url):
                    continue

            try:
                self._parse_repo(self.temp_dir, repo_name, branch)
            except Exception as e:
                self.log(msg=str(e), tag="parseRepo Error Caught")
                self.log(tag="", msg=traceback.format_exc())

            os.chdir(self.curr_dir)
            if not self.config.dry and self.config.delete_temp:
                shutil.rmtree(self.temp_dir)

    def _scan_local_repos(self):
        if "local_repos" not in self.config.config:
            self.log(msg="", tag="No local repos", display=True)
            return

        localrepos = self.config.config["local_repos"]
        if not localrepos:
            self.log(msg="", tag="No local repos", display=True)
            return

        for repo_path in localrepos:
            split_url = repo_path.split("@")
            branch = None
            if len(split_url) == 2:
                branch = split_url[1]
                repo_path = split_url[0]

            repo_name = self._get_repo_name(repo_path)
            self._parse_repo(repo_path, repo_name, branch)

    def _get_repo_name(self, repo_path):
        a = Path(repo_path).absolute()
        if match := re.search(r"([^/]*\.git.*)", str(a)):
            return match[1]
        return os.path.basename(os.path.normpath(repo_path))
