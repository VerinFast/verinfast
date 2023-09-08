#!/usr/bin/env python3

import argparse
import json
import platform
import subprocess
import os
import yaml
import httpx
import shutil
# import sys
import re

from verinfast.utils.utils import DebugLog

from verinfast.cloud.aws.costs import runAws
from verinfast.cloud.azure.costs import runAzure
from verinfast.cloud.aws.instances import get_instances as get_aws_instances
from verinfast.cloud.azure.instances import get_instances as get_az_instances
from verinfast.cloud.gcp.instances import get_instances as get_gcp_instances
from verinfast.cloud.aws.blocks import getBlocks as get_aws_blocks
from verinfast.cloud.azure.blocks import getBlocks as get_az_blocks
from verinfast.cloud.gcp.blocks import getBlocks as get_gcp_blocks

from verinfast.dependencies.walk import walk as dependency_walk

# from modernmetric.fp import file_process
# If we want to run modernmetric directly

requestx = httpx.Client(http2=True, timeout=None)

shouldUpload = False
shouldManualFileScan = True

runGit = True
runSizes = True
runStats = True
runScan = True
runDependencies = True

dry = False  # Flag to not run scans, just upload files (if shouldUpload==True)
config = FileNotFoundError
reportId = 0
corsisId = 0
baseUrl = ''

uname = platform.uname()
system = uname.system
node = uname.node
release = uname.release
version = uname.version
machine = uname.machine

output_dir = os.path.join(os.getcwd(), "results")

debugLog = DebugLog(os.getcwd())

debugLog.log(msg='', tag="Started")


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verinfast",
        usage="%(prog)s [OPTION] [FILE]...",
        # TODO: Description
        # description="Print or check SHA1 (160-bit) checksums."
    )
    parser.add_argument(
        "-c", "--config",
        dest="config"
    )

    parser.add_argument(
        "-o", "--output", "--output_dir",
        dest="output_dir"
    )

    return parser


def main():
    global shouldUpload
    global shouldManualFileScan
    global dry
    global reportId
    global baseUrl
    global corsisId
    global config
    global output_dir

    global runGit
    global runSizes
    global runStats
    global runScan
    global runDependencies

    parser = init_argparse()
    args = parser.parse_args()

    cfg_path = "config.yaml"
    if "config" in args and args.config is not None:
        cfg_path = args.config

    if "output_dir" in args and args.output_dir is not None:
        output_dir = os.path.join(os.getcwd(), args.output_dir)

    os.makedirs(output_dir, exist_ok=True)

    # print(cfg_path)
    # sys.exit(0)

    # Read the config file
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    debugLog.log(msg=config, tag="Config", display=True)

    global_dependencies()

    shouldUpload = config['should_upload']

    runGit = config['run_git'] if 'run_git' in config else runGit
    runSizes = config['run_sizes'] if 'run_sizes' in config else runSizes
    runStats = config['run_stats'] if 'run_stats' in config else runStats
    runScan = config['run_scan'] if 'run_scan' in config else runScan
    runDependencies = config['run_dependencies'] if 'run_dependencies' in config else runDependencies

    shouldManualFileScan = config['should_manual_filescan'] if 'should_manual_filescan' in config else shouldManualFileScan
    debugLog.log(msg=shouldUpload, tag="Should upload", display=True)
    reportId = config['report']['id']
    baseUrl = config['baseurl']

    if "modules" in config:
        if "code" in config["modules"]:

            dry = config['modules']['code']['dry']

            # Check if Git is installed
            checkDependency("git", "Git")

            # Check if Modernmetric is installed
            checkDependency("modernmetric", "ModernMetric")

            # Check if SEMGrep is installed
            checkDependency("semgrep", "SEMGrep")

            if shouldUpload:
                headers = {
                    'content-type': 'application/json',
                    'Accept-Charset': 'UTF-8',
                }
                debugLog.log(msg=f"{baseUrl}/report/{reportId}/CorsisCode", tag="Report Run Id Fetch", display=True)
                response = requestx.get(f"{baseUrl}/report/{reportId}/CorsisCode", headers=headers)
                corsisId = response.text
                if corsisId and corsisId != '':
                    debugLog.log(msg=corsisId, tag="Report Run Id", display=True)
                else:
                    raise Exception(f"{corsisId} returned for failed report Id fetch.")
            else:
                print("ID only fetched for upload")
            scanRepos(config)
        if "cloud" in config['modules']:
            scanCloud(config)

    debugLog.log(msg='', tag="Finished")

# #### Helpers #####
# newline = "\n" # TODO - Set to system appropriate newline character. This doesn't work with modernmetric


# Excludes files in .git directories. Takes path of full path with filename
def allowfile(path, allowDir=False):
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
def get_raw_size(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if (os.path.isfile(fp) and not os.path.islink(fp)):
                total_size += os.path.getsize(fp)  # os.stat(fp).st_size
    return total_size


# Simple algorithm for lines of code in a file
def getloc(file):
    try:
        count = 0
        with open(file) as fp:
            for line in fp:
                if line.strip():
                    count += 1
        return count
    except:
        return 0


# Truncate large strings for display
def truncate(text, length=100):
    testStr = str(text)  # Supports passing in Lists and other types
    return ((testStr[:length] + '..') if len(testStr) > length else testStr)


# Chunk a list
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ##### Setup ######
def checkDependency(command, name):
    which = shutil.which(command)
    if not which:
        debugLog.log(msg=f"{name} is required but it's not installed.", tag=f"{name} status", display=False)
        raise Exception(f"{name} is required but it's not installed.")
    else:
        debugLog.log(msg=f"{name} is installed at {which}.", tag=f"{name} status", display=True)


def global_dependencies():
    # Check if Python3 is installed. This would catch if run with Python 2
    checkDependency("python3", "Python3")


# #### Upload #####
def upload(file, route, source=''):
    global shouldUpload
    global baseUrl

    if shouldUpload:
        with open(file, 'rb') as f:
            debugLog.log(msg=f"{baseUrl}{route}", tag="Uploading to")
            headers = {
                'Content-Type': 'application/json',
                'accept': 'application/json'
            }
            response = requestx.post(baseUrl + route, data=f, headers=headers)
        if response.status_code == 200:
            debugLog.log(msg='', tag=f"Successfully uploaded {file} for {source} to {baseUrl}{route}.", display=True)
        else:
            debugLog.log(msg=response.status_code, tag=f"Failed to upload {file} for {source} to {baseUrl}{route}", display=True)


# ### Helpers2 #####
def escapeChars(text: str):
    fixedText = re.sub(r'([\"\{\}])', r'\\\1', text)
    return fixedText


def trimLineBreaks(text: str):
    return text.replace("\n", "").replace("\r", "")


def formatGitHash(hash: str):
    message = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%B", hash]).decode('utf-8')
    author = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%aN <%aE>", hash]).decode('utf-8')
    commit = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%H", hash]).decode('utf-8')
    date = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%aD", hash]).decode('utf-8')
    returnVal = {
        "message": trimLineBreaks(message),
        "author": author,
        "commit": commit,
        "date": escapeChars(date)
    }
    return returnVal


def parseRepo(path: str, repo_name: str):
    global output_dir

    print('parseRepo')
    if not dry:
        os.chdir(path)

    # Get Correct Branch
    # TODO Get a list of branches and use most recent if no main or master
    branch = ""
    try:
        if not dry:
            subprocess.check_call(["git", f"--work-tree={path}", "checkout", "main"])
            branch = "main"
    except subprocess.CalledProcessError:
        try:
            if not dry:
                subprocess.check_call(["git", "checkout", "master"])
                branch = "master"
        except subprocess.CalledProcessError:
            raise Exception("Error checking out branch from git.")
    branch = branch.strip()

    # Git Stats
    if runGit:
        debugLog.log(msg=repo_name, tag="Gathering source code statistics for", display=True)
        command = f'''git log \
            --since="{config["modules"]["code"]["git"]["start"]}" \
            --numstat \
            --format='%H' \
            {branch} --
        '''
        try:
            if not dry:
                results = subprocess.run(command, shell=True, stdout=subprocess.PIPE)
                log = results.stdout.decode()
        except subprocess.CalledProcessError:
            raise Exception("Error getting log from git.")

        if not dry:
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
                            hashObj = formatGitHash(prevHash)
                            hashObj['paths'] = filesArr
                            finalArr.append(hashObj)
                            filesArr = []
                        prevHash = lineArr[0]

            debugLog.log(msg=truncate(finalArr), tag=f"{repo_name} Git Stats")

        git_output_file = os.path.join(output_dir, repo_name + ".git.log.json")

        if not dry:
            with open(git_output_file, 'w') as f:
                f.write(json.dumps(finalArr, indent=4))

        upload(git_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/git", repo_name)

        # Manual File Sizes and Info
        if not dry:
            debugLog.log(msg=repo_name, tag="Gathering file sizes for", display=True)
            # Sizes for writing to output file
            # Intialize file list with "." as total size
            repo_size = get_raw_size(".")
            git_size = get_raw_size("./.git")

            # get sizes
            real_size = repo_size - git_size
            debugLog.log(msg=repo_size, tag="Repo Size")
            debugLog.log(msg=git_size, tag="Git Size")
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
                    if allowfile(path=fp):
                        if shouldManualFileScan:
                            file = {
                                "size": os.path.getsize(fp),
                                "loc": getloc(fp),
                                "ext": ext,  # os.path.splitext(name)[1],
                                "directory": False
                            }
                            sizes["files"][fp] = file
                        filelist.append({"name": name, "path": fp})

        sizes_output_file = os.path.join(output_dir, repo_name + ".sizes.json")

        if not dry:
            with open(sizes_output_file, 'w') as f:
                f.write(json.dumps(sizes, indent=4))
        upload(sizes_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/sizes", repo_name)

    # Run Modernmetric
    if runStats:
        stats_input_file = os.path.join(output_dir, repo_name + ".filelist.json")
        stats_output_file = os.path.join(output_dir, repo_name + ".stats.json")
        stats_error_file = os.path.join(output_dir, repo_name + ".stats.err")

        if not dry:
            debugLog.log(msg=repo_name, tag="Analyzing repository with Modernmetric", display=True)
            with open(stats_input_file, 'w') as f:
                f.write(json.dumps(filelist, indent=4))

            # Calling modernmetric with subprocess works, but we might want to call
            # Modernmetric directly, ala lines 91-110 from modernmetric main
            with open(stats_output_file, 'w') as f:
                with open(stats_error_file, 'w') as e:
                    subprocess.check_call(["modernmetric", f"--file={stats_input_file}"], stdout=f, stderr=e, encoding='utf-8')

        upload(stats_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/stats", repo_name)

    # Run SEMGrep
    if runScan:
        findings_output_file = os.path.join(output_dir, repo_name + ".findings.json")
        findings_error_file = os.path.join(output_dir, repo_name + ".findings.err")
        if not dry:
            debugLog.log(msg=repo_name, tag="Scanning repository", display=True)
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
                debugLog.log(msg=output, tag="Scanning repository return", display=True)
        upload(findings_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/findings", repo_name)

# ##### Scan Dependencies ######
    if runDependencies:
        dependencies_output_file = os.path.join(output_dir, repo_name + ".dependencies.json")
        debugLog.log(msg=repo_name, tag="Scanning dependencies", display=True)
        if not dry:
            dependencies_file = dependency_walk(output_file=dependencies_output_file)
            debugLog.log(msg=dependencies_file, tag="Dependency File", display=False)
        upload(dependencies_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/dependencies", repo_name)


# ##### Scan Repos ######
def scanRepos(config):

    # Loop over all remote repositories from config file
    if 'repos' in config:
        repos = config['repos']
        if repos:
            for repo_url in repos:
                match = re.search(".*\/(.*)", repo_url)
                repo_name = match.group(1)
                debugLog.log(msg=repo_name, tag="Processing", display=True)
                curr_dir = os.getcwd()
                temp_dir = os.path.join(curr_dir, "temp_repo")
                if not dry:
                    os.makedirs(temp_dir, exist_ok=True)
                debugLog.log(msg=repo_url, tag="Repo URL")
                debugLog.log(msg=temp_dir, tag="Temp Directory")
                if not dry:
                    try:
                        # subprocess.check_call(["git", "clone", repo_url, temp_dir])
                        subprocess.check_output(["git", "clone", repo_url, temp_dir])
                    except subprocess.CalledProcessError:
                        debugLog.log(msg=repo_url, tag="Failed to clone", display=True)
                        exit(1)
                        continue

                    debugLog.log(msg=repo_url, tag="Successfully cloned", display=True)

                parseRepo(temp_dir, repo_name)

                os.chdir(curr_dir)
                if not dry:
                    shutil.rmtree(temp_dir)
        else:
            debugLog.log(msg='', tag="No remote repos", display=True)
    else:
        debugLog.log(msg='', tag="No remote repos", display=True)

    # Loop over all local repositories from config file
    if 'local_repos' in config:
        localrepos = config['local_repos']
        if localrepos:
            for repo_path in localrepos:
                match = re.search(".*\/(.*)", repo_path)
                repo_name = match.group(1)
                parseRepo(repo_path, repo_name)
        else:
            debugLog.log(msg='', tag="No local repos", display=True)
    else:
        debugLog.log(msg='', tag="No local repos", display=True)

        debugLog.log(msg='', tag="Finished repo scans")


# ##### Scan Cloud ######
def scanCloud(config):
    debugLog.log(msg='', tag="Doing cloud scan", display=True)
    cloud_config = config['modules']['cloud']
    debugLog.log(msg=cloud_config, tag='Cloud Config')

    if cloud_config is None:
        return

    for provider in cloud_config:
        if provider["provider"] == "aws":
            # Check if AWS-CLI is installed
            checkDependency("aws", "AWS Command-line tool")

            aws_cost_file = runAws(targeted_account=provider["account"], start=provider["start"], end=provider["end"], path_to_output=output_dir)
            debugLog.log(msg=aws_cost_file, tag="AWS Costs")
            upload(file=aws_cost_file, route=f"/report/{config['report']['id']}/Costs", source="AWS")
            aws_instance_file = get_aws_instances(sub_id=provider["account"], path_to_output=output_dir)
            if aws_instance_file is not None:
                upload(file=aws_instance_file, route=f"/report/{config['report']['id']}/instances", source="AWS")
                aws_utilization_file = aws_instance_file[:-5] + "-utilization.json"
                upload(file=aws_utilization_file, route=f"/report/{config['report']['id']}/instance_utilization", source="AWS")
            aws_block_file = get_aws_blocks(sub_id=provider["account"], path_to_output=output_dir)
            debugLog.log(msg=aws_block_file)
            upload(file=aws_block_file, route=f"/report/{config['report']['id']}/storage", source="AWS")

        if provider["provider"] == "azure":
            # Check if Azure CLI is installed
            checkDependency("az", "Azure Command-line tool")

            azure_cost_file = runAzure(subscription_id=provider["account"], start=provider["start"], end=provider["end"], path_to_output=output_dir)
            debugLog.log(msg=azure_cost_file, tag="Azure Costs")
            upload(file=azure_cost_file, route=f"/report/{config['report']['id']}/Costs", source="Azure")
            azure_instance_file = get_az_instances(sub_id=provider["account"], path_to_output=output_dir)
            debugLog.log(msg=azure_instance_file, tag="Azure instances")
            upload(file=azure_instance_file, route=f"/report/{config['report']['id']}/instances", source="Azure")
            azure_utilization_file = azure_instance_file[:-5] + "-utilization.json"
            upload(file=azure_utilization_file, route=f"/report/{config['report']['id']}/instance_utilization", source="Azure")
            azure_block_file = get_az_blocks(sub_id=provider["account"], path_to_output=output_dir)
            debugLog.log(msg=azure_block_file, tag="Azure Storage")
            upload(file=azure_block_file, route=f"/report/{config['report']['id']}/storage", source="Azure")

        if provider["provider"] == "gcp":
            # Check if Google Cloud CLI is installed
            checkDependency("gcloud", "Google Command-line tool")

            gcp_instance_file = get_gcp_instances(sub_id=provider["account"], path_to_output=output_dir)
            debugLog.log(msg=gcp_instance_file, tag="GCP instances")
            upload(file=gcp_instance_file, route=f"/report/{config['report']['id']}/instances", source="GCP")
            gcp_utilization_file = gcp_instance_file[:-5] + "-utilization.json"
            upload(file=gcp_utilization_file, route=f"/report/{config['report']['id']}/instance_utilization", source="GCP")
            gcp_block_file = get_gcp_blocks(sub_id=provider["account"], path_to_output=output_dir)
            debugLog.log(msg=gcp_block_file, tag="GCP Storage")
            upload(file=gcp_block_file, route=f"/report/{config['report']['id']}/storage", source="GCP")
