import os
import shutil
import subprocess
from verinfast.utils.utils import std_exec, trimLineBreaks, escapeChars


class GitUtils:
    def _prepare_temp_directory(self):
        try:
            if not self.config.dry:
                os.makedirs(self.temp_dir)
        except Exception as e:
            self.log(
                tag="Directory exists:",
                msg=self.temp_dir,
                display=True,
            )
            try:
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir)
            except Exception as e:
                self.log(
                    tag=f"Failed to delete {self.temp_dir}",
                    msg=e,
                    display=True,
                )
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
                subprocess.check_call(
                    ["git", f"--work-tree={path}", "checkout", branch]
                )
            except subprocess.CalledProcessError:
                try:
                    subprocess.check_call(["git", "checkout", "master"])
                except subprocess.CalledProcessError:
                    try:
                        cmd = "git for-each-ref --count=1 --sort=-committerdate refs/heads/ --format='%(refname:short)'"
                        branch = (
                            std_exec(cmd.split(" ")).replace("'", "").replace("\n", "")
                        )
                        subprocess.check_call(["git", "checkout", branch])
                    except subprocess.CalledProcessError:
                        if self.config.runGit:
                            raise Exception("Error checking out branch from git.")
                        else:
                            self.log("Error checking out branch from git.")

    def _format_git_hash(self, hash: str):
        hash = hash.replace("'", "").replace('"', "")
        message = std_exec(["git", "log", "-n1", "--pretty=format:%B", hash], self.log)
        author = std_exec(
            ["git", "log", "-n1", "--pretty=format:%aN <%aE>", hash], self.log
        )
        commit = std_exec(["git", "log", "-n1", "--pretty=format:%H", hash], self.log)
        date = std_exec(["git", "log", "-n1", "--pretty=format:%aD", hash], self.log)
        signed = std_exec(["git", "show", "--format='%G?'", hash], self.log)
        if signed != "N":
            signed = True
        else:
            signed = False
        merge = False
        merge1 = std_exec(["git", "show", hash], self.log)
        if merge1.startswith("Merge: "):
            merge = True
        returnVal = {
            "message": trimLineBreaks(message),
            "author": author,
            "commit": commit,
            "date": escapeChars(date),
            "signed": signed,
            "merge": merge,
        }
        return returnVal

    def _process_git_log(self, branch):
        """Process git log and return results"""
        command = f"""git log \
            --since="{self.config.modules.code.git.start}" \
            --numstat \
            --format='%H' \
            {branch} --
        """

        if self.config.dry:
            return []

        results = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
        log = results.stdout.decode()

        resultArr = log.split("\n")
        prevHash = ""
        filesArr = []
        finalArr = []

        for line in resultArr:
            lineArr = line.split("\t")
            if len(lineArr) > 1:
                filesArr.append(
                    {
                        "insertions": lineArr[0],
                        "deletions": lineArr[1],
                        "path": lineArr[2],
                    }
                )
            else:
                if len(lineArr) == 1 and lineArr[0] != "":
                    if prevHash:
                        hashObj = self._format_git_hash(prevHash)
                        hashObj["paths"] = filesArr
                        finalArr.append(hashObj)
                        filesArr = []
                    prevHash = lineArr[0]

        return finalArr
