import os
import shutil
import subprocess
from verinfast.utils.utils import std_exec


class GitUtils:
    def _prepare_temp_directory(self):
        try:
            if not self.config.dry:
                os.makedirs(self.temp_dir)
        except:
            self.log(tag="Directory exists:", msg=self.temp_dir, display=True)
            try:
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir)
            except Exception as e:
                self.log(tag=f"Failed to delete {self.temp_dir}", msg=e, display=True)
                return False
        return True

    def _clone_repository(self, repo_url):
        try:
            subprocess.check_output(["git", "clone", repo_url, self.temp_dir])
            self.log(msg=repo_url, tag="Successfully cloned", display=True)
            return True
        except subprocess.CalledProcessError:
            self.log(msg=repo_url, tag="Failed to clone", display=True)
            return False

    def _initialize_git(self, path, branch):
        """Initialize and checkout git repository"""
        if not self.config.dry:
            subprocess.check_call(["git", "init"])
            try:
                subprocess.check_call(["git", f"--work-tree={path}", "checkout", branch])
            except subprocess.CalledProcessError:
                try:
                    subprocess.check_call(["git", "checkout", "master"])
                except subprocess.CalledProcessError:
                    try:
                        cmd = "git for-each-ref --count=1 --sort=-committerdate refs/heads/ --format='%(refname:short)'"
                        branch = std_exec(cmd.split(" ")).replace("'", "").replace("\n", "")
                        subprocess.check_call(["git", "checkout", branch])
                    except subprocess.CalledProcessError:
                        if self.config.runGit:
                            raise Exception("Error checking out branch from git.")
                        else:
                            self.log("Error checking out branch from git.")
