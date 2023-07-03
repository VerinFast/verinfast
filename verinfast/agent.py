#!/usr/bin/env python3
#
#  Welcome to the Scanning Agent.
#
#  This tool safely and securely analyzes applications for benchmarking.
#
#  Requirements:
#  - Python3 - Test with "python3 --version"
#  - Pip - Test with "pip -V"
#  - SSH access to code repositories - Test with "git status"
#  - Command line tool access to cloud hosting providers
#  - Admin privileges on the computer used to run the agent.
#
#  To run the Agent:
#  - Install this package with "python3 setup.py install --user"
#  - In a directory with a "config.yaml" file run
#    "verinfast"
#
#  Troubleshooting:
#  Python
#  - Run "python3 -m pip install --upgrade pip setuptools wheel"
#  Git
#  - Run "which git", "git --version"
#  - Run " ssh -vT git@github.com" to test access to GitHub
#   AWS
#  - Run "which aws", "aws --version"
#  Azure
#  - Run "az git", "az --version"
#  - Run "az account subscription list" to check subscription Id
#  Semgrep
#  - Run "which semgrep", "semgrep --version"
#  Pip
#  - Run "which pip"
#  - If no Pip, run:
#     curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py
#     python get-pip.py  OR python3 get-pip.py
#  Run "sudo apt update"
#
#  Copyright 2023 Startos Inc.
#
##################################################################################

import json
import platform
import subprocess
import os
import time
import yaml
import requests
import shutil
import re

from utils.utils import debugLog
from cloud.aws import runAws
from cloud.az_parse import runAzure
#from modernmetric.fp import file_process # If we want to run modernmetric directly

shouldUpload = False
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
os.makedirs(output_dir, exist_ok=True)

debugLog(msg='', tag="Started")

def main():
    global shouldUpload
    global reportId
    global baseUrl
    global corsisId
    global config

    # Read the config file
    with open('config.yaml') as f:
        config = yaml.safe_load(f)
    debugLog(msg=config,tag="Config", display=True)

    global_dependencies()

    shouldUpload = config['should_upload']
    debugLog(msg=shouldUpload, tag="Should upload", display=True)
    reportId = config['report']['id']
    baseUrl = config['baseurl']

    if "modules" in config:
        if "code" in config["modules"]:

            # Check if Git is installed
            checkDependency("git", "Git")

            # Check if Modernmetric is installed
            checkDependency("modernmetric", "ModernMetric")

            # Check if SEMGrep is installed
            checkDependency("semgrep", "SEMGrep")

            if shouldUpload:
                headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
                corsisId = requests.get(f"{baseUrl}/report/{reportId}/CorsisCode", headers=headers).content.decode('utf-8')
                debugLog(corsisId, "Report Run Id", True)
            else :
                print("ID only fetched for upload")
            scanRepos(config)
        if "cloud" in config['modules']:
            scanCloud(config)

    debugLog(msg='', tag="Finished")

##### Helpers #####
#newline = "\n" # TODO - Set to system appropriate newline character. This doesn't work with modernmetric

# Excludes files in .git directories. Takes path of full path with filename
def allowfile(path):
    normpath = os.path.normpath(path)
    dirlist = normpath.split(os.sep)
    if ("node_modules" not in dirlist and
        ".git" not in dirlist and
        os.path.isfile(path) and 
        not os.path.islink(path)):
        return True
    else:
        return False

# Get recursive size of a directory
def get_raw_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if(os.path.isfile(fp) and not os.path.islink(fp)):
                total_size += os.path.getsize(fp) #os.stat(fp).st_size
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
    testStr = str(text) # Supports passing in Lists and other types
    return((testStr[:length] + '..') if len(testStr) > length else testStr)

###### Setup ######
def checkDependency(command, name):
    if not shutil.which(command):
        debugLog(f"{name} is required but it's not installed.", f"{name} status", False)
        raise Exception(f"{name} is required but it's not installed.")
    else:
        debugLog(f"{name} is installed.", f"{name} status", True)

def global_dependencies():
    # Check if Python3 is installed. This would catch if run with Python 2
    checkDependency("python3", "Python3")

##### Upload #####
def upload(file, route, source=''):
    global shouldUpload
    global baseUrl

    if shouldUpload:
        with open(file, 'rb') as f:
            debugLog(f"{baseUrl}{route}", f"Uploading to")
            headers = {
                'Content-Type': 'application/json', 
                'accept': 'application/json'
            }
            response = requests.post(baseUrl + route, data=f, headers=headers)
        if response.status_code == 200:
            debugLog('', f"Successfully uploaded {file} for {source} to {baseUrl}{route}.", True)
        else:
            debugLog(response.status_code, f"Failed to upload {file} for {source} to {baseUrl}{route}", True)

#### Helpers2 #####
def escapeChars(text:str):
    fixedText = re.sub(r'([\"\{\}])', r'\\\1', text)
    return(fixedText)

def trimLineBreaks(text:str):
    return(text.replace("\n", "").replace("\r",""))

def formatGitHash(hash:str):
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

def parseRepo(path:str, repo_name:str):
    os.chdir(path)

    # Get Correct Branch
    # TODO Get a list of branches and use most recent if no main or master
    branch=""
    try:
        subprocess.check_call(["git", "checkout", "main"])
        branch="main"
    except subprocess.CalledProcessError:
        try:
            subprocess.check_call(["git", "checkout", "master"])
            branch="master"
        except subprocess.CalledProcessError:
            raise Exception("Error checking out branch from git.")
    branch=branch.strip()

    # Git Stats
    debugLog(repo_name, "Gathering source code statistics for", True)
    command = f'''git log \
        --since="{config["modules"]["code"]["git"]["start"]}" \
        --numstat \
        --format='%H' \
        {branch} --
    '''
    try:
        results=subprocess.run(command, shell=True, stdout=subprocess.PIPE)
        log = results.stdout.decode()
    except subprocess.CalledProcessError:
        raise Exception("Error getting log from git.")

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

    debugLog(truncate(finalArr), f"{repo_name} Git Stats")

    git_output_file = os.path.join(output_dir, repo_name + ".git.log.json")
    with open(git_output_file, 'w') as f:
        f.write(json.dumps(finalArr, indent=4))
    upload(git_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/git", repo_name)

    # File Sizes and Info
    debugLog(repo_name, "Gathering file sizes for", True)
    # Sizes for writing to output file
    # Intialize file list with "." as total size
    repo_size = get_raw_size(".")
    git_size = get_raw_size("./.git")

    # get sizes
    real_size= repo_size - git_size
    debugLog(repo_size, "Repo Size")
    debugLog(git_size, "Git Size")
    sizes = {
        "files":{
            ".":{
                "size" : repo_size,
                "loc" : 0,
                "ext" : None,
                "directory" : True
            }
        },
        "metadata":{
            "env": machine,
            "real_size": real_size,
            "uname": system
        }
    }
    #filelist for modernmetric
    filelist = []

    for filepath, subdirs, list in os.walk("."):
        for name in list:
            fp = os.path.join(filepath, name)
            extRe = re.search("^[^\.]*\.(.*)", name)
            ext = extRe.group(1) if extRe else ''
            if allowfile(fp):
                file = {
                    "size" : os.path.getsize(fp),
                    "loc" : getloc(fp),
                    "ext" : ext, #os.path.splitext(name)[1],
                    "directory" : False
                }
                sizes["files"][fp] = file
                filelist.append(fp)

    sizes_output_file = os.path.join(output_dir, repo_name + ".sizes.json")
    with open(sizes_output_file, 'w') as f:
        f.write(json.dumps(sizes, indent=4))
    upload(sizes_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/sizes", repo_name)

    # Run Modernmetric
    debugLog(repo_name, "Analyzing repository with Modernmetric", True)

    stats_output_file = os.path.join(output_dir, repo_name + ".stats.json")
    stats_error_file = os.path.join(output_dir, repo_name + ".stats.err")

    # Calling modernmetric with subproccess works, but we might want to call
    # Modernmetric directly, ala lines 91-110 from modernmetric main
    with open(stats_output_file, 'w') as f:
        with open(stats_error_file, 'w') as e:
            subprocess.check_call(["modernmetric"] + filelist, stdout=f, stderr=e, encoding='utf-8')
    upload(stats_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/stats", repo_name)

    # Run SEMGrep
    debugLog(repo_name, "Scanning repository", True)
    findings_output_file = os.path.join(output_dir, repo_name + ".findings.json")
    findings_error_file = os.path.join(output_dir, repo_name + ".findings.err")
    with open(findings_error_file, 'a') as e:
        subprocess.check_output([
            "semgrep",
            "scan",
            "--config",
            "auto",
            "--json",
            "-o",
            findings_output_file,
        ], stderr=e,)
    upload(findings_output_file, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/findings", repo_name)

###### Scan Repos ######
def scanRepos(config):

    # Loop over all remote repositories from config file
    repos = config['repos']
    if repos:
        for repo_url in repos:
            match = re.search(".*\/(.*)", repo_url)
            repo_name = match.group(1)
            debugLog(repo_name, "Processing", True)
            curr_dir = os.getcwd()
            temp_dir = os.path.join(curr_dir, "temp_repo")
            os.makedirs(temp_dir, exist_ok=True)
            debugLog(msg=repo_url, tag="Repo URL")
            debugLog(msg=temp_dir, tag="Temp Directory")
            try:
                #subprocess.check_call(["git", "clone", repo_url, temp_dir])
                subprocess.check_output(["git", "clone", repo_url, temp_dir])
            except subprocess.CalledProcessError:
                debugLog(repo_url, "Failed to clone", True)
                exit(1)
                continue

            debugLog(repo_url, "Successfully cloned", True)

            parseRepo(temp_dir, repo_name)

            os.chdir(curr_dir)

            shutil.rmtree(temp_dir)
    else:
        debugLog('', "No remote repos", True)

    # Loop over all local repositories from config file
    localrepos = config['local_repos']
    if localrepos:
        for repo_path in localrepos:
            match = re.search(".*\/(.*)", repo_path)
            repo_name = match.group(1)
            parseRepo(repo_path, repo_name)
    else:
        debugLog('', "No local repos", True)

    debugLog(time.strftime("%H:%M:%S", time.localtime()), "Finished repo scans")

###### Scan Cloud ######
def scanCloud(config):
    print("Doing cloud scan")
    # TODO Here support multiple providers

    cloud_config = config['modules']['cloud']
    print(cloud_config)

    if None == cloud_config:
        return

    for provider in cloud_config:
        if(provider["provider"] == "aws"):
            # Check if AWS-CLI is installed
            checkDependency("aws", "AWS Command-line tool")

            aws_file = runAws(targeted_account=provider["account"], start=provider["start"], end=provider["end"], path_to_output=output_dir)
            debugLog(msg=aws_file, tag="AWS Results")
            upload(file=aws_file, route=f"/report/{config['report']['id']}/Costs", source="AWS")
        
        if(provider["provider"] == "azure"):
            # Check if AWS-CLI is installed
            checkDependency("az", "Azure Command-line tool")

            azure_file = runAzure(subscription_id=provider["account"], start=provider["start"], end=provider["end"], path_to_output=output_dir)
            debugLog(msg=azure_file, tag="Azure Results")
            upload(file=azure_file, route=f"/report/{config['report']['id']}/Costs", source="Azure")


# For test runs from commandline. Comment out before packaging.
main()
