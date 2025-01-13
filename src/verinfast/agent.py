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
import contextlib
import io
from uuid import uuid4

from modernmetric.__main__ import main as modernmetric
import semgrep.commands.scan as semgrep_scan

import httpx
from jinja2 import Environment, FileSystemLoader
from pygments_tsx.tsx import patch_pygments

from verinfast.utils.utils import DebugLog, std_exec, trimLineBreaks, escapeChars, truncate, truncate_children, get_repo_name_url_and_branch
from verinfast.upload import Uploader
from verinfast.cloud.aws.costs import runAws
from verinfast.cloud.aws.get_profile import find_profile
from verinfast.cloud.azure.costs import runAzure
from verinfast.cloud.aws.instances import get_instances as get_aws_instances
from verinfast.cloud.azure.instances import get_instances as get_az_instances
from verinfast.cloud.gcp.instances import get_instances as get_gcp_instances
from verinfast.cloud.aws.blocks import getBlocks as get_aws_blocks
from verinfast.cloud.azure.blocks import getBlocks as get_az_blocks
from verinfast.cloud.gcp.blocks import getBlocks as get_gcp_blocks
from verinfast.config import Config
from verinfast.user import initial_prompt, save_path, repeat_boolean_prompt
from verinfast.utils.license import report as report_license

from verinfast.dependencies.walk import walk as dependency_walk


patch_pygments()

today = date.today()

requestx = httpx.Client(http2=True, timeout=None)
uname = platform.uname()
system = uname.system
node = uname.node
release = uname.release
version = uname.version
machine = uname.machine


template_definition = {}

file_path = Path(__file__)
parent_folder = file_path.parent.absolute()
templates_folder = str(parent_folder.joinpath("templates"))
# str_path = str(parent_folder.joinpath('str_conf.yaml').absolute())

curr_dir = os.getcwd()
temp_dir = Path(os.path.expanduser('~/.verinfast/')).joinpath('temp_repo')


class Agent:
    def __init__(self):
        self.config = Config()
        os.makedirs(self.config.output_dir, exist_ok=True)
        self.debug = DebugLog(file=self.config.log_file, debug=False)
        self.log = self.debug.log
        self.log(msg='', tag="Started")
        self.uploader = Uploader(self.config.upload_conf)
        self.up = self.uploader.make_upload_path
        self.config.upload_logs = initial_prompt()
        self.directory = save_path()

    def create_template(self):
        if not self.config.dry:
            with open(f"{self.config.output_dir}/results.html", "w") as f:
                jinja_env = Environment(loader=FileSystemLoader(templates_folder))
                jinja_env.globals.update(zip=zip, sorted=sorted)
                output = jinja_env.get_template("results.j2").render(template_definition)
                f.write(output)

    def scan(self):
        if self.config.modules is not None:
            if self.config.modules.code is not None:

                if self.config.shouldUpload:
                    headers = {
                        'content-type': 'application/json',
                        'Accept-Charset': 'UTF-8',
                    }
                    get_url = self.uploader.make_upload_path("scan_id", report=self.config.reportId)
                    self.log(msg=f"{self.config.baseUrl}{get_url}", tag="Report Run Id Fetch", display=True)
                    response = requestx.get(f"{self.config.baseUrl}{get_url}", headers=headers)
                    self.scanId = response.text.replace("'", "").replace('"', '')
                    if self.scanId and self.scanId != '':
                        self.log(msg=self.scanId, tag="Report Run Id", display=True)
                    else:
                        raise Exception(f"{self.scanId} returned for failed report Id fetch.")
                else:
                    self.log(msg="Scan ID only fetched when uploading enabled", tag="Scan ID", display=True)
                self.scanRepos()
            if self.config.modules and self.config.modules.cloud and len(self.config.modules.cloud):
                self.scanCloud()
            try:
                self.create_template()
            except:
                self.log(tag="ERROR", msg="Template Creation Failed")
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
            self.log(msg=f"{name} is required but it's not installed.", tag=f"{name} status", display=False, timestamp=False)
            if kill:
                raise Exception(f"{name} is required but it's not installed.")
            return False
        else:
            self.log(msg=f"{name} is installed at {which}.", tag=f"{name} status", display=True, timestamp=False)
            return True

    def upload(self, file: str, route: str, source: str = '', isJSON=True):
        if not self.config.shouldUpload:
            self.log(
                msg='Skipping Uploads',
                tag=f"Skipping uploading {file} for {source} to {self.config.baseUrl}/{route}.",
                display=True
            )
            return True
        if not Path(file).exists():
            self.log(
                msg=f"File does not exist: {file}"
            )
            return False

        orig_route = route

        route = self.up(
            path_type=route,
            report=self.config.reportId,
            code=self.scanId,
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
            return True
        else:
            self.log(
                msg=response.status_code,
                tag=f"Failed to upload {file} for {source} to {self.config.baseUrl}{route}",
                display=True
            )
            return False

    def formatGitHash(self, hash: str):
        hash = hash.replace("'", "").replace('"', "")
        message = std_exec(["git", "log", "-n1", "--pretty=format:%B", hash], self.log)
        author = std_exec(["git", "log", "-n1", "--pretty=format:%aN <%aE>", hash], self.log)
        commit = std_exec(["git", "log", "-n1", "--pretty=format:%H", hash], self.log)
        date = std_exec(["git", "log", "-n1", "--pretty=format:%aD", hash], self.log)
        signed = std_exec(["git", "show", "--format='%G?'", hash], self.log)
        if signed != 'N':
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
            "merge": merge
        }
        return returnVal

    def parseRepo(self, path: str, repo_name: str, branch: str = None):
        self.log(msg='parseRepo')

        if not self.config.dry:
            os.chdir(path)

        if branch is None:
            branch = "main"

        # Adding this for Windows support
        # Appears to fail with blank HEAD
        if self.config.runGit:
            std_exec(["git", "init"])

        if self.config.runGit and self.checkDependency("git", "Git"):
            try:
                if not self.config.dry:
                    subprocess.check_call(["git", f"--work-tree={path}", "checkout", branch])
            except subprocess.CalledProcessError:
                try:
                    if not self.config.dry:
                        subprocess.check_call(["git", "checkout", "master"])
                        branch = "master"
                except subprocess.CalledProcessError:
                    try:
                        cmd = "git for-each-ref --count=1 --sort=-committerdate refs/heads/ --format='%(refname:short)'"
                        # remove new lines and apostrophes from branch name.
                        branch = std_exec(cmd.split(" ")).replace("'", "").replace("\n", "")
                        subprocess.check_call(["git", "checkout", branch])
                    except subprocess.CalledProcessError:
                        if self.config.runGit:
                            raise Exception("Error checking out branch from git.")
                        else:
                            self.log("Error checking out branch from git.")

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
                            if prevHash:
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
                template_definition["gitlog"] = finalArr
                # End if not self.config.dry:

        # if Path(git_output_file).exists():
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
                    "uname": system,
                    "branch": locals()['branch'] if "branch" in locals() else None
                }
            }

            # filelist for modernmetric
            filelist = []

            for filepath, subdirs, list in os.walk("."):
                for name in list:
                    fp = os.path.join(filepath, name)
                    extRe = re.search(r"^[^\.]*\.(.*)", name)
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
            template_definition["current_dir_size"] = sizes["files"].pop(".")
            template_definition["sizes"] = sizes
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

            if not self.config.dry:
                self.log(msg=repo_name, tag="Analyzing repository with Modernmetric", display=True)
                with open(stats_input_file, 'w') as f:
                    f.write(json.dumps(filelist, indent=4))

                template_definition["filelist"] = filelist
                custom_args = [f"--file={stats_input_file}", f"--output={stats_output_file}"]
                modernmetric(custom_args=custom_args, license_identifier=self.config.reportId)
                report_license(self.config.reportId, self.config, "modernmetric")

                with open(stats_output_file, 'r') as f:
                    template_definition["stats"] = json.load(f)
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

            findings_output_file = os.path.join(self.config.output_dir, repo_name + ".findings.json")
            findings_success = False
            if not self.config.dry:
                self.log(msg=repo_name, tag="Scanning repository", display=True)
                try:
                    with open(findings_output_file, 'a') as o:
                        custom_args = [
                            "--config",
                            "auto",
                            "--json",
                            f"--json-output={findings_output_file}",
                            "-q"
                        ]
                        try:
                            with contextlib.redirect_stdout(io.StringIO()):
                                semgrep_scan.scan(custom_args)
                            findings_success = True
                        except SystemExit as e:
                            if e.code == 0:
                                findings_success = True
                            else:
                                self.log(tag="ERROR", msg="SystemExit in Semgrep")
                                self.log(e)
                except Exception as e:
                    self.log(tag="ERROR", msg="Error in Semgrep")
                    self.log(e)
            if findings_success:
                try:
                    with open(findings_output_file) as f:
                        findings = json.load(f)

                    # This is on purpose. If you try to read same pointer
                    # twice, it dies.
                    with open(findings_output_file) as f:
                        original_findings = json.load(f)

                    if self.config.truncate_findings:
                        # Exclusions are set to exclude fields that are not code
                        truncation_exclusion = [
                            "cwe",
                            "owasp",
                            "path",
                            "check_id",
                            "license",
                            "fingerprint",
                            "message",
                            "references",
                            "url",
                            "source",
                            "severity"
                        ]
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
                    template_definition["gitfindings"] = findings
                except Exception as e:
                    if not self.config.dry:
                        self.log(tag="ERROR", msg="Error in findings post-processing")
                        self.log(e)
                    else:
                        self.log(
                            msg=f'''
                                Attempted to format/truncate non existent file
                                {findings_output_file}
                            '''
                        )
            # End if findings_success is True

            # Upload findings always, in case of dry run
            # .upload checks should_upload
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
                with open(dependencies_output_file, "r") as f:
                    template_definition["dependencies"] = json.load(f)
            self.log(msg=dependencies_output_file, tag="Dependency File", display=False)
            self.upload(
                file=dependencies_output_file,
                route="dependencies",
                source=repo_name
            )

    def preflight(self):
        # If the 'dry' configuration is set, skip the preflight checks
        if self.config.dry:
            return

        # Loop over all remote repositories from config file
        print("\n\n\nChecking your system's compatibility with the scan configuration:\n")
        if 'repos' in self.config.config:
            repos = self.config.config["repos"]
            if repos:
                for repo_url in [r for r in repos if len(r) > 0]:       # ignore blank lines from server
                    match = re.search(r"([^/]*\.git.*)", repo_url)
                    if match:
                        repo_name = match.group(1)
                    else:
                        repo_name = repo_url.rsplit('/', 1)[-1]
                    if "@" in repo_name and re.search(r"^.*@.*\..*:", repo_url):
                        repo_url = "@".join(repo_url.split("@")[0:2])
                    elif "@" in repo_name:
                        repo_url = repo_url.split("@")[0]
                    try:
                        subprocess.check_output(["git", "ls-remote", repo_url])
                        self.log(tag="Repository access confirmed", msg=repo_url, display=True, timestamp=False)
                    except subprocess.CalledProcessError:
                        self.log(msg=repo_url, tag="Unable to access", display=True, timestamp=False)
                        self.log(msg=repo_url, tag="Repository will not be scanned", display=True, timestamp=False)

        cloud_config = self.config.modules.cloud
        if cloud_config is not None:
            for provider in cloud_config:
                try:
                    if provider.provider == "aws" and self.checkDependency("aws", "AWS Command-line tool"):
                        account_id = str(provider.account).replace('-', '')
                        if find_profile(account_id, self.log) is None:
                            self.log(tag=f"No matching AWS CLI profiles found for {provider.account}", msg="Account can't be scanned.", display=True, timestamp=False)
                        else:
                            self.log(tag="AWS account access confirmed", msg=account_id, display=True, timestamp=False)
                    if provider.provider == "azure" and self.checkDependency("az", "Azure Command-line tool"):
                        pass
                    if provider.provider == "gcp" and self.checkDependency("gcloud", "Google Command-line tool"):
                        pass
                except:
                    self.log(msg=f"Unable to access {provider.provider} {provider.account}", tag="Unable to access", display=True, timestamp=False)

        resp = repeat_boolean_prompt(
            "\nWould you like to proceed with the scan?",
            logger=print,
            default_val=True
        )

        if resp:
            self.log(msg="Proceeding")
        else:
            self.log(tag="Exiting now", msg="", display=True)
            exit(0)

    # ##### Scan Repos ######
    def scanRepos(self):
        # Loop over all remote repositories from config file
        if 'repos' in self.config.config:
            repos = self.config.config["repos"]
            if repos:
                for repo_url in [r for r in repos if len(r) > 0]:       # ignore blank lines from server
                    repo_info = get_repo_name_url_and_branch(repo_url)
                    repo_name = repo_info["repo_name"]
                    repo_url = repo_info["repo_url"]
                    branch = repo_info["branch"]
                    self.log(msg=repo_name, tag="Processing", display=True)
                    self.log(msg=repo_url, tag="URL", display=True)
                    self.log(msg=branch, tag="Branch Specified", display=True)
                    try:
                        if not self.config.dry:
                            os.makedirs(temp_dir)
                    except:
                        self.log(tag="Directory exists:", msg=temp_dir, display=True)
                        try:
                            shutil.rmtree(temp_dir)
                            os.makedirs(temp_dir)
                        except Exception as e:
                            self.log(tag=f"Failed to delete {temp_dir}", msg=e, display=True)
                            continue

                    self.log(msg=repo_url, tag="Repo URL")
                    self.log(msg=temp_dir, tag="Temp Directory")
                    if not self.config.dry and self.config.runGit:
                        try:
                            subprocess.check_output(["git", "clone", repo_url, temp_dir])
                        except subprocess.CalledProcessError:
                            self.log(msg=repo_url, tag="Failed to clone", display=True)
                            continue

                        self.log(msg=repo_url, tag="Successfully cloned", display=True)
                    try:
                        self.parseRepo(temp_dir, repo_name, branch)
                    except Exception as e:
                        self.log(msg=str(e), tag="parseRepo Error Caught")
                        self.log(tag="", msg=traceback.format_exc())

                    os.chdir(curr_dir)
                    if not self.config.dry and self.config.delete_temp:
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

                    # Check for a branch
                    split_url = repo_path.split("@")
                    branch = None
                    if len(split_url) == 2:
                        branch = split_url[1]
                        repo_path = split_url[0]

                    a = Path(repo_path).absolute()
                    match = re.search(r"([^/]*\.git.*)", str(a))
                    if match:
                        repo_name = match.group(1)
                    else:
                        repo_name = os.path.basename(os.path.normpath(repo_path))
                    self.parseRepo(repo_path, repo_name, branch)
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
            try:
                # Check if AWS-CLI is installed
                if provider.provider == "aws" and self.checkDependency("aws", "AWS Command-line tool"):
                    account_id = str(provider.account).replace('-', '')
                    aws_cost_file = runAws(
                        targeted_account=account_id,
                        start=provider.start,
                        end=provider.end,
                        profile=provider.profile,
                        path_to_output=self.config.output_dir,
                        log=self.log,
                        dry=self.config.dry
                    )
                    if aws_cost_file is None:
                        self.log(msg="Error processing AWS costs", tag=account_id)
                    else:
                        self.log(msg=aws_cost_file, tag="AWS Costs")
                        self.upload(
                            file=aws_cost_file,
                            route="costs",
                            source="AWS"
                        )
                    aws_instance_file = get_aws_instances(
                        sub_id=account_id,
                        path_to_output=self.config.output_dir,
                        dry=self.config.dry
                    )
                    if aws_instance_file is None:
                        self.log(msg="Error processing AWS instances", tag=account_id)
                    else:
                        self.log(msg=aws_instance_file, tag="AWS Instances")
                        self.upload(
                            file=aws_instance_file,
                            route="instances",
                            source="AWS"
                        )
                    aws_utilization_file = os.path.join(
                        self.config.output_dir,
                        f'aws-instances-{account_id}-utilization.json'
                    )
                    if Path(aws_utilization_file).is_file():
                        self.upload(
                            file=aws_utilization_file,
                            route="utilization",
                            source="AWS"
                        )
                    aws_block_file = get_aws_blocks(
                        sub_id=account_id,
                        path_to_output=self.config.output_dir,
                        log=self.log,
                        dry=self.config.dry
                    )
                    if aws_block_file is None:
                        self.log(msg="Error processing AWS blocks", tag=account_id)
                    else:
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
                        path_to_output=self.config.output_dir,
                        log=self.log,
                        dry=self.config.dry
                    )
                    if azure_cost_file is None:
                        self.log(msg="Error processing Azure costs", tag=provider.account)
                    else:
                        self.log(msg=azure_cost_file, tag="Azure Costs")
                        self.upload(
                            file=azure_cost_file,
                            route="costs",
                            source="Azure"
                        )
                    azure_instance_file = get_az_instances(
                        sub_id=provider.account,
                        path_to_output=self.config.output_dir,
                        dry=self.config.dry,
                        log=self.log
                    )
                    if azure_instance_file is None:
                        self.log(msg="Error processing Azure instances", tag=provider.account)
                    else:
                        self.log(msg=azure_instance_file, tag="Azure instances")
                        self.upload(
                            file=azure_instance_file,
                            route="instances",
                            source="Azure"
                        )
                    azure_utilization_file = os.path.join(
                        self.config.output_dir,
                        f'az-instances-{provider.account}-utilization.json'
                    )
                    if Path(azure_utilization_file).is_file():
                        self.upload(
                            file=azure_utilization_file,
                            route="utilization",
                            source="AWS"
                        )
                    azure_block_file = get_az_blocks(
                        sub_id=provider.account,
                        path_to_output=self.config.output_dir,
                        dry=self.config.dry
                    )
                    if azure_block_file is None:
                        self.log(msg="Error processing Azure blocks", tag=provider.account)
                    else:
                        self.log(msg=azure_block_file, tag="Azure Storage")
                        self.upload(
                            file=azure_block_file,
                            route="storage",
                            source="Azure"
                        )

                if provider.provider == "gcp" and self.checkDependency("gcloud", "Google Command-line tool"):
                    gcp_instance_file = get_gcp_instances(
                        sub_id=provider.account,
                        path_to_output=self.config.output_dir,
                        dry=self.config.dry
                    )
                    if gcp_instance_file is None:
                        self.log(msg="Error processing GCP instances", tag=provider.account)
                    else:
                        self.log(msg=gcp_instance_file, tag="GCP instances")
                        self.upload(
                            file=gcp_instance_file,
                            route="instances",
                            source="GCP"
                        )
                    gcp_utilization_file = os.path.join(
                        self.config.output_dir,
                        f'gcp-instances-{provider.account}-utilization.json'
                    )
                    if Path(gcp_utilization_file).is_file():
                        self.upload(
                            file=gcp_utilization_file,
                            route="utilization",
                            source="AWS"
                        )
                    gcp_block_file = get_gcp_blocks(
                        sub_id=provider.account,
                        path_to_output=self.config.output_dir,
                        dry=self.config.dry
                    )
                    if gcp_block_file is None:
                        self.log(msg="Error processing GCP blocks", tag=provider.account)
                    else:
                        self.log(msg=gcp_block_file, tag="GCP Storage")
                        self.upload(
                            file=gcp_block_file,
                            route="storage",
                            source="GCP"
                        )
            except Exception as e:
                self.log(tag="ERROR", msg="Error processing provider", display=True)
                self.log(
                    tag="ERROR PROVIDER",
                    msg=str(provider),
                    display=True
                )
                self.log(tag="ERROR", msg=e, display=True)
                self.log(
                    tag="ERROR STACK",
                    msg=traceback.format_exc()
                )


def main():
    agent = Agent()
    try:
        agent.preflight()
        agent.scan()
    except Exception as e:
        agent.log(msg=str(e), tag="Main Scan Error Caught")
        if agent.config.upload_logs:
            agent.upload(route="logs", file=agent.config.output_dir+"/log.txt")
        raise e

    # If user opts to upload logs, copy the log to the verinfast directory for future upload
    if agent.config.upload_logs:
        new_folder_name = (
            str(today.year) + str(today.month) + str(today.day)
        )
        d = agent.directory
        os.makedirs(f'{d}/{new_folder_name}/', exist_ok=True)
        new_file_name = str(uuid4())+".txt"
        fp = f'{d}/{new_folder_name}/{new_file_name}'
        shutil.copy2(agent.config.log_file, fp)
        print(f"""The log for this run was copied to:
            {d}/{new_folder_name}/{new_file_name}""")

    # If user opts to upload results, upload and non-uploaded logs
    if agent.config.shouldUpload:
        log_list = os.listdir(agent.config.output_dir)
        log_list.sort()  # Upload current log last
        for file in log_list:
            if file.endswith("log.txt") and not file.startswith("u_"):
                file_path = os.path.join(agent.config.output_dir, file)
                agent.upload(
                    route="logs",
                    file=file_path,
                    source=file,
                    isJSON=False
                )
                new_path = os.path.join(agent.config.output_dir, "u_"+file)
                os.rename(file_path, new_path)

    # We only do this if you have a remote config but didn't upload
    if not agent.config.shouldUpload and agent.config.is_original_path_remote():
        print("\n\n\nIMPORTANT: To upload results from this location please run")
        print(f"verinfast -c {agent.config.cfg_path} -o {agent.config.output_dir} --should_upload --dry")


if __name__ == "__main__":
    main()
# For test runs from commandline. Comment out before packaging. # main()
