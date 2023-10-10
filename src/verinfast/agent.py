#!/usr/bin/env python3
from datetime import date
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import traceback
from uuid import uuid4

import httpx
from pygments_tsx.tsx import patch_pygments

from verinfast.utils.utils import DebugLog, std_exec, trimLineBreaks, escapeChars, truncate, truncate_children
from verinfast.upload import Uploader

from verinfast.cloud.aws.costs import runAws
from verinfast.cloud.azure.costs import runAzure
from verinfast.cloud.aws.instances import get_instances as get_aws_instances
from verinfast.cloud.azure.instances import get_instances as get_az_instances
from verinfast.cloud.gcp.instances import get_instances as get_gcp_instances
from verinfast.cloud.aws.blocks import getBlocks as get_aws_blocks
from verinfast.cloud.azure.blocks import getBlocks as get_az_blocks
from verinfast.cloud.gcp.blocks import getBlocks as get_gcp_blocks
from verinfast.config import Config
from verinfast.user import initial_prompt, save_path

from verinfast.dependencies.walk import walk as dependency_walk

# from verinfast.pygments_patch import patch_pygments
# from modernmetric.fp import file_process
# If we want to run modernmetric directly

patch_pygments()

today = date.today()

requestx = httpx.Client(http2=True, timeout=None)
uname = platform.uname()
system = uname.system
node = uname.node
release = uname.release
version = uname.version
machine = uname.machine


class Agent:
    def __init__(self):
        self.config = Config()
        os.makedirs(self.config.output_dir, exist_ok=True)
        self.debug = DebugLog(path=self.config.output_dir, debug=False)
        self.log = self.debug.log
        self.log(msg='', tag="Started")
        self.uploader = Uploader(self.config.upload_conf)
        self.up = self.uploader.make_upload_path
        self.config.upload_logs = initial_prompt()
        self.directory = save_path()

    def scan(self):
        if self.config.modules is not None:
            if self.config.modules.code is not None:
                # Check if Git is installed
                self.checkDependency("git", "Git")

                if self.config.shouldUpload:
                    headers = {
                        'content-type': 'application/json',
                        'Accept-Charset': 'UTF-8',
                    }
                    get_url = self.uploader.make_upload_path("scan_id", report=self.config.reportId)
                    self.log(msg=f"{self.config.baseUrl}{get_url}", tag="Report Run Id Fetch", display=True)
                    response = requestx.get(f"{self.config.baseUrl}{get_url}", headers=headers)
                    self.corsisId = response.text.replace("'", "").replace('"', '')
                    if self.corsisId and self.corsisId != '':
                        self.log(msg=self.corsisId, tag="Report Run Id", display=True)
                    else:
                        raise Exception(f"{self.corsisId} returned for failed report Id fetch.")
                else:
                    print("ID only fetched for upload")
                self.scanRepos()
            if self.config.modules and self.config.modules.cloud and len(self.config.modules.cloud):
                self.scanCloud()

        self.log(msg='', tag="Finished")

    # Excludes files in .git directories. Takes path of full path with filename
    def allowfile(self, path, allowDir=False):
        normpath = os.path.normpath(path)
        dirlist = normpath.split(os.sep)
        if (
            "node_modules" not in dirlist and
            ".git" not in dirlist and
            not os.path.islink(path) and
            (os.path.isfile(path) or allowDir)
        ):
            return True
        else:
            return False

    # Get recursive size of a directory
    def get_raw_size(self, start_path='.'):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if (os.path.isfile(fp) and not os.path.islink(fp)):
                    total_size += os.path.getsize(fp)  # os.stat(fp).st_size
        return total_size

    # Simple algorithm for lines of code in a file
    def getloc(self, file):
        try:
            count = 0
            with open(file) as fp:
                for line in fp:
                    if line.strip():
                        count += 1
            return count
        except:
            return 0

    def checkDependency(self, command, name, kill=False) -> bool:
        which = shutil.which(command)
        if not which:
            self.log(msg=f"{name} is required but it's not installed.", tag=f"{name} status", display=False)
            if kill:
                raise Exception(f"{name} is required but it's not installed.")
            return False
        else:
            self.log(msg=f"{name} is installed at {which}.", tag=f"{name} status", display=True)
            return True

    def upload(self, file: str, route: str, source: str = '', isJSON=True):
        if not self.config.shouldUpload:
            self.log(
                msg='Skipping Uploads',
                tag=f"Skipping uploading {file} for {source} to {self.config.baseUrl}{route}.",
                display=True
            )
            return
        if not Path(file).exists():
            return

        orig_route = route

        route = self.up(
            path_type=route,
            report=self.config.reportId,
            code=self.corsisId,
            repo_name=source
        )

        with open(file, 'rb') as f:
            self.log(msg=f"{self.config.baseUrl}{route}", tag="Uploading to")

            if isJSON:
                headers = {
                    'Content-Type': 'application/json',
                    'accept': 'application/json'
                }
                response = requestx.post(self.config.baseUrl + route, data=f, headers=headers)
            else:
                files = {'logFile': f}
                response = requestx.post(self.config.baseUrl + route, files=files)

        if response.status_code == 200:
            self.log(
                msg='',
                tag=f"Successfully uploaded {file} for {source} to {self.config.baseUrl}{route}.",
                display=True
            )
            try:
                err_path_str = file[0:-5]+'.err'
                err_path = Path(err_path_str)

                if err_path.exists():
                    self.upload(
                        file=err_path_str,
                        route="err_"+orig_route,
                        source=source+" Error Logs",
                        isJSON=False
                    )
            except:
                pass
        else:
            self.log(
                msg=response.status_code,
                tag=f"Failed to upload {file} for {source} to {self.config.baseUrl}{route}",
                display=True
            )

    def formatGitHash(self, hash: str):
        message = std_exec(["git", "log", "-n1", "--pretty=format:%B", hash])
        author = std_exec(["git", "log", "-n1", "--pretty=format:%aN <%aE>", hash])
        commit = std_exec(["git", "log", "-n1", "--pretty=format:%H", hash])
        date = std_exec(["git", "log", "-n1", "--pretty=format:%aD", hash])
        returnVal = {
            "message": trimLineBreaks(message),
            "author": author,
            "commit": commit,
            "date": escapeChars(date)
        }
        return returnVal

    def parseRepo(self, path: str, repo_name: str):
        self.log(msg='parseRepo')
        if not self.config.dry:
            os.chdir(path)
        if self.config.runGit and self.checkDependency("git", "Git"):
            # Get Correct Branch
            # TODO Get a list of branches and use most recent if no main or master
            branch = "main"
            if "@" in repo_name:
                branch = repo_name.split("@")[1]
                repo_name = repo_name.split("@")[0]
            try:
                if not self.config.dry:
                    subprocess.check_call(["git", f"--work-tree={path}", "checkout", branch])
            except subprocess.CalledProcessError:
                try:
                    if not self.config.dry:
                        subprocess.check_call(["git", "checkout", "master"])
                        branch = "master"
                except subprocess.CalledProcessError:
                    if self.config.runGit:
                        raise Exception("Error checking out branch from git.")
                    else:
                        self.log("Error checking out branch from git.")
            branch = branch.strip()

        # Git Stats
        git_output_file = os.path.join(self.config.output_dir, repo_name + ".git.log.json")
        if self.config.runGit:
            self.log(msg=repo_name, tag="Gathering source code statistics for", display=True)
            command = f'''git log \
                --since="{self.config.modules.code.git.start}" \
                --numstat \
                --format='%H' \
                {branch} --
            '''
            try:
                if not self.config.dry:
                    results = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
                    log = results.stdout.decode()
            except subprocess.CalledProcessError:
                self.log("Error getting log from git")
                raise Exception("Error getting log from git.")

            if not self.config.dry:
                resultArr = log.split("\n")
                prevHash = ''
                filesArr = []
                finalArr = []

                for line in resultArr:
                    lineArr = line.split("\t")
                    if len(lineArr) > 1:
                        filesArr.append({
                            "insertions": lineArr[0],
                            "deletions": lineArr[1],
                            "path": lineArr[2]
                        })
                    else:
                        if len(lineArr) == 1 and lineArr[0] != '':
                            # Hit next file
                            if prevHash != '':
                                # Not first one
                                hashObj = self.formatGitHash(prevHash)
                                hashObj['paths'] = filesArr
                                finalArr.append(hashObj)
                                filesArr = []
                            prevHash = lineArr[0]

                self.log(msg=truncate(finalArr), tag=f"{repo_name} Git Stats")

                self.log(msg=git_output_file, display=True)

                with open(git_output_file, 'w') as f:
                    f.write(json.dumps(finalArr, indent=4))
                # End if not self.config.dry:

        if Path(git_output_file).exists():
            self.upload(
                file=git_output_file,
                route="git",
                source=repo_name
            )

        # Manual File Sizes and Info
        sizes_output_file = os.path.join(self.config.output_dir, repo_name + ".sizes.json")

        if not self.config.dry:
            self.log(msg=repo_name, tag="Gathering file sizes for", display=True)
            # Sizes for writing to output file
            # Intialize file list with "." as total size
            repo_size = self.get_raw_size(".")
            git_size = self.get_raw_size("./.git")

            # get sizes
            real_size = repo_size - git_size
            self.log(msg=repo_size, tag="Repo Size")
            self.log(msg=git_size, tag="Git Size")
            sizes = {
                "files": {
                    ".": {
                        "size": repo_size,
                        "loc": 0,
                        "ext": None,
                        "directory": True
                    }
                },
                "metadata": {
                    "env": machine,
                    "real_size": real_size,
                    "uname": system
                }
            }

            # filelist for modernmetric
            filelist = []

            for filepath, subdirs, list in os.walk("."):
                # print(subdirs)
                for name in list:
                    fp = os.path.join(filepath, name)
                    extRe = re.search("^[^\.]*\.(.*)", name)
                    ext = extRe.group(1) if extRe else ''
                    if self.allowfile(path=fp):
                        if self.config.shouldManualFileScan:
                            file = {
                                "size": os.path.getsize(fp),
                                "loc": self.getloc(fp),
                                "ext": ext,  # os.path.splitext(name)[1],
                                "directory": False
                            }
                            sizes["files"][fp] = file
                        filelist.append({"name": name, "path": fp})

            with open(sizes_output_file, 'w') as f:
                f.write(json.dumps(sizes, indent=4))
            # End if not self.config.dry:

        self.upload(
            file=sizes_output_file,
            route="sizes",
            source=repo_name
        )

        # Run Modernmetric
        if self.config.runStats:
            stats_input_file = os.path.join(self.config.output_dir, repo_name + ".filelist.json")
            stats_output_file = os.path.join(self.config.output_dir, repo_name + ".stats.json")
            stats_error_file = os.path.join(self.config.output_dir, repo_name + ".stats.err")

            if not self.config.dry:
                self.log(msg=repo_name, tag="Analyzing repository with Modernmetric", display=True)
                with open(stats_input_file, 'w') as f:
                    f.write(json.dumps(filelist, indent=4))

                # Calling modernmetric with subprocess works, but we might want to call
                # Modernmetric directly, ala lines 91-110 from modernmetric main
                with open(stats_output_file, 'w') as f:
                    with open(stats_error_file, 'w') as e:
                        subprocess.check_call(["modernmetric", f"--file={stats_input_file}"], stdout=f, stderr=e, encoding='utf-8')

            self.upload(
                file=stats_output_file,
                route="stats",
                source=repo_name
            )

        # Run SEMGrep
        if self.config.runScan:
            if system.lower() == 'windows':
                self.log("""
                Windows does not support Semgrep.
                Please see the open issues here:
                https://github.com/returntocorp/semgrep/issues/1330
                         """)
            if self.checkDependency('semgrep', "Semgrep"):
                findings_output_file = os.path.join(self.config.output_dir, repo_name + ".findings.json")
                findings_error_file = os.path.join(self.config.output_dir, repo_name + ".findings.err")
                if not self.config.dry:
                    self.log(msg=repo_name, tag="Scanning repository", display=True)
                    try:
                        with open(findings_error_file, 'a') as e:
                            subprocess.check_call([
                                "semgrep",
                                "scan",
                                "--config",
                                "auto",
                                "--json",
                                "-o",
                                findings_output_file,
                            ], stderr=e,)
                    except subprocess.CalledProcessError as e:
                        output = e.output
                        self.log(msg=output, tag="Scanning repository return", display=True)
                try:
                    with open(findings_output_file) as f:
                        findings = json.load(f)

                    # This is on purpose. If you try to read same pointer
                    # twice, it dies.
                    with open(findings_output_file) as f:
                        original_findings = json.load(f)

                    if self.config.truncate_findings:
                        truncation_exclusion = ["cwe", "path", "check_id", "license"]
                        self.log(
                            tag="TRUNCATING",
                            msg=f"excluding: {truncation_exclusion}"
                        )
                        try:
                            findings = truncate_children(
                                findings,
                                self.log,
                                excludes=truncation_exclusion,
                                max_length=self.config.truncate_findings_length
                            )
                        except Exception as e:
                            self.log(tag="ERROR", msg="Error in Truncation")
                            self.log(e)
                            self.log(
                                json.dumps(
                                    original_findings,
                                    indent=4,
                                    sort_keys=True
                                )
                            )
                    with open(findings_output_file, "w") as f2:
                        f2.write(json.dumps(
                            findings, indent=4, sort_keys=True
                        ))
                except Exception as e:
                    if not self.config.dry:
                        raise e
                    else:
                        self.log(
                            msg=f'''
                                Attempted to format/truncate non existent file
                                {findings_output_file}
                            '''
                        )
                self.upload(
                    file=findings_output_file,
                    route="findings",
                    source=repo_name
                )

        # ##### Scan Dependencies ######
        if self.config.runDependencies:
            dependencies_output_file = os.path.join(self.config.output_dir, repo_name + ".dependencies.json")
            self.log(msg=repo_name, tag="Scanning dependencies", display=True)
            if not self.config.dry:
                dependencies_output_file = dependency_walk(output_file=dependencies_output_file, logger=self.log)
            self.log(msg=dependencies_output_file, tag="Dependency File", display=False)
            self.upload(
                file=dependencies_output_file,
                route="dependencies",
                source=repo_name
            )

    # ##### Scan Repos ######
    def scanRepos(self):
        # Loop over all remote repositories from config file
        if 'repos' in self.config.config:
            repos = self.config.config["repos"]
            if repos:
                for repo_url in repos:
                    match = re.search(".*\/(.*)", repo_url)
                    repo_name = match.group(1)
                    if "@" in repo_name:
                        repo_url = "@".join(repo_url.split("@")[0:2])

                    self.log(msg=repo_name, tag="Processing", display=True)
                    curr_dir = os.getcwd()
                    temp_dir = os.path.join(curr_dir, "temp_repo")
                    if not self.config.dry:
                        os.makedirs(temp_dir, exist_ok=True)
                    self.log(msg=repo_url, tag="Repo URL")
                    self.log(msg=temp_dir, tag="Temp Directory")
                    if not self.config.dry and self.config.runGit:
                        try:
                            subprocess.check_output(["git", "clone", repo_url, temp_dir])
                        except subprocess.CalledProcessError:
                            self.log(msg=repo_url, tag="Failed to clone", display=True)
                            exit(1)
                            continue

                        self.log(msg=repo_url, tag="Successfully cloned", display=True)
                    try:
                        self.parseRepo(temp_dir, repo_name)
                    except Exception as e:
                        self.log(msg=str(e), tag="parseRepo Error Caught")
                        self.log(tag="", msg=traceback.format_exc())

                    os.chdir(curr_dir)
                    if not self.config.dry:
                        shutil.rmtree(temp_dir)
            else:
                self.log(msg='', tag="No remote repos", display=True)

        else:
            self.log(msg='', tag="No remote repos", display=True)

        # Loop over all local repositories from config file
        if 'local_repos' in self.config.config:
            localrepos = self.config.config['local_repos']
            if localrepos:
                for repo_path in localrepos:
                    a = Path(repo_path).absolute()
                    match = re.search(".*\/(.*)", str(a))
                    repo_name = match.group(1)
                    self.parseRepo(repo_path, repo_name)
            else:
                self.log(msg='', tag="No local repos", display=True)
        else:
            self.log(msg='', tag="No local repos", display=True)

        self.log(msg='', tag="Finished repo scans")

    # ##### Scan Cloud ######
    def scanCloud(self):
        self.log(msg='', tag="Doing cloud scan", display=True)
        cloud_config = self.config.modules.cloud
        self.log(msg=cloud_config, tag='Cloud Config')

        if cloud_config is None:
            return

        for provider in cloud_config:
            # Check if AWS-CLI is installed
            if provider.provider == "aws" and self.checkDependency("aws", "AWS Command-line tool"):
                aws_cost_file = runAws(
                    targeted_account=provider.account,
                    start=provider.start,
                    end=provider.end,
                    profile=provider.profile,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=aws_cost_file, tag="AWS Costs")
                self.upload(
                    file=aws_cost_file,
                    route="costs",
                    source="AWS"
                )
                aws_instance_file = get_aws_instances(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=aws_instance_file, tag="AWS Instances")
                self.upload(
                    file=aws_instance_file,
                    route="instances",
                    source="AWS"
                )
                aws_utilization_file = aws_instance_file[:-5] + "-utilization.json"
                self.upload(
                    file=aws_utilization_file,
                    route="utilization",
                    source="AWS"
                )
                aws_block_file = get_aws_blocks(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=aws_block_file, tag="AWS Storage")
                self.upload(
                    file=aws_block_file,
                    route="storage",
                    source="AWS"
                )

            # Check if Azure CLI is installed
            if provider.provider == "azure" and self.checkDependency("az", "Azure Command-line tool"):
                azure_cost_file = runAzure(
                    subscription_id=provider.account,
                    start=provider.start,
                    end=provider.end,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=azure_cost_file, tag="Azure Costs")
                self.upload(
                    file=azure_cost_file,
                    route="costs",
                    source="Azure"
                )
                azure_instance_file = get_az_instances(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=azure_instance_file, tag="Azure instances")
                self.upload(
                    file=azure_instance_file,
                    route="instances",
                    source="Azure"
                )
                azure_utilization_file = azure_instance_file[:-5] + "-utilization.json"
                self.upload(
                    file=azure_utilization_file,
                    route="utilization",
                    source="AWS"
                )
                azure_block_file = get_az_blocks(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=azure_block_file, tag="Azure Storage")
                self.upload(
                    file=azure_block_file,
                    route="storage",
                    source="Azure"
                )

            if provider.provider == "gcp" and self.checkDependency("gcloud", "Google Command-line tool"):
                gcp_instance_file = get_gcp_instances(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=gcp_instance_file, tag="GCP instances")
                self.upload(
                    file=gcp_instance_file,
                    route="instances",
                    source="GCP"
                )
                gcp_utilization_file = gcp_instance_file[:-5] + "-utilization.json"
                self.upload(
                    file=gcp_utilization_file,
                    route="utilization",
                    source="AWS"
                )
                gcp_block_file = get_gcp_blocks(
                    sub_id=provider.account,
                    path_to_output=self.config.output_dir
                )
                self.log(msg=gcp_block_file, tag="GCP Storage")
                self.upload(
                    file=gcp_block_file,
                    route="storage",
                    source="GCP"
                )


def main():
    agent = Agent()
    try:
        agent.scan()
    except Exception as e:
        agent.log(msg=str(e), tag="Main Scan Error Caught")
        if agent.config.upload_logs:
            agent.upload(route="logs", file=agent.config.output_dir+"/log.txt")
        raise e
    if agent.config.upload_logs:
        agent.upload(route="logs", file=agent.config.output_dir+"/log.txt", source='logs', isJSON=False)
        new_folder_name = (
            str(today.year) + str(today.month) + str(today.day)
        )
        d = agent.directory
        os.makedirs(f'{d}/{new_folder_name}/', exist_ok=True)
        new_file_name = str(uuid4())+".txt"
        fp = f'{d}/{new_folder_name}/{new_file_name}'
        shutil.copy2(agent.config.output_dir+"/log.txt", fp)
        os.unlink(agent.config.output_dir+"/log.txt")
        print(f"""The log for this run has moved to:
              {d}/{new_folder_name}/{new_file_name}""")


if __name__ == "__main__":
    main()
# For test runs from commandline. Comment out before packaging. # main()
