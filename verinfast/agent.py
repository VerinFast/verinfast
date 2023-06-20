#!/usr/bin/env python3
#
#  Welcome to the Scanning Agent.
#
#  This tool safely and securely analyzes applications for benchmarking.
#
#  Requirements:
#  - Python3 - Test with "python3 --version"
#  - Pip - Test with "pip -V"
#  - SSH access to code repositories
#  - Command line tool access to cloud hosting providers
#  - Admin privileges on the computer used to run the agent.
#
#  To run the Agent:
#  - Install this package with "python3 setup.py install"
#  - In a directory with a "config.yaml" file run
#    "verinfast"
#
#  Troubleshooting:
#  - Run "python3 -m pip install --upgrade pip setuptools wheel"
#
#  Copyright 2023 Startos Inc.
#
##################################################################################

import json
import subprocess
import importlib
import sys
import os
import yaml
import requests
import shutil
import re
#from multimetric.fp import file_process # If we want to run multimetric directly
import semgrep
import jc

shouldUpload = False
config = FileNotFoundError
reportId = 0
corsisId = 0
baseUrl = ''
modules_code_git_start = ''

debug=True

def debugLog(msg, tag='Debug Log:'):
    if debug:
        print(f"{tag} {msg}")

def main():
    config = setup()
    print("Config:")
    print(config)

    shouldUpload = config['should_upload']
    reportId = config['report']['id']
    baseUrl = config['baseurl']
    modules_code_git_start = config['baseurl'] #config['modules']['code']['git']['start']

    if shouldUpload:
        headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
        corsisId = requests.get(f"{baseUrl}/report/{reportId}/CorsisCode", headers=headers)
    else :
        print("ID only fetched for upload")
    scan(config)

##### Helpers #####
newline = "\n" # TODO - Set to system appropriate newline character. This doesn't work with multimetric

# Excludes files in .git directories. Takes path of full path with filename
def allowfile(path):
    gitpattern = re.compile("^(.*\.git.*)$")
    if not gitpattern.match(path) and os.path.isfile(path) and not os.path.islink(path):
        return True
    else:
        return False

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if allowfile(fp):
                total_size += os.path.getsize(fp)
    return total_size

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

###### Setup ######
def setup():
    # Read the config file
    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    # Check if Python3 is installed. This would catch if run with Python 2
    if not shutil.which("python3"):
        raise Exception("Python3 is required but it's not installed.")

    print("Python3 is installed.")

    # Check if Git is installed
    if not shutil.which("git"):
        raise Exception("Git is required but it's not installed.")

    print("Git is installed.")

    return config

##### Upload #####
def upload(file, route, repo=''):
    if shouldUpload:
        with open(file, 'rb') as f:
            response = requests.post(baseUrl + route, files={'file': f})
        if response.status_code == 200:
            print(f"Successfully uploaded {file} for {repo} to the {route}.")
        else:
            print(f"Failed to upload {file} for {repo} to the {route}.")

#### Helpers #####
def escapeChars(text):
    debugLog(text, "text")
    fixedText = re.sub(r'([\"\{\}])', r'\\\1', text)
    debugLog(fixedText, "fixedText")
    return(fixedText)

def trimLineBreaks(text):
    return(text.replace("\n", "").replace("\r",""))

def formatGitHash(hash):
    message = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%B", hash]).decode('utf-8')
    author = subprocess.check_output(["git", "log", "-n1", "--pretty=format:'%aN <%aE>'", hash]).decode('utf-8')
    commit = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%H", hash]).decode('utf-8')
    date = subprocess.check_output(["git", "log", "-n1", "--pretty=format:%aD", hash]).decode('utf-8')
    debugLog(message, "message")
    returnVal = {
        "message": trimLineBreaks(message),
        "author": author,
        "commit": commit,
        "date": escapeChars(date)
    }
    debugLog(returnVal, "returnVal")
    return returnVal

###### Scan ######
def scan(config):
    output_dir = os.path.join(os.getcwd(), "results")
    os.makedirs(output_dir, exist_ok=True)

    # Loop over all repositories from config file
    for repo_url in config['repos']:

        match = re.search("#*\/(.*)", repo_url)
        repo_name = match.group(1)
        print(f"Processing {repo_name}")
        temp_dir = os.path.join(os.getcwd(), "temp_repo")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            subprocess.check_call(["git", "clone", repo_url, temp_dir])
        except subprocess.CalledProcessError:
            print(f"Failed to clone {repo_url}")
            continue

        print(f"Successfully cloned {repo_url}")

        os.chdir(temp_dir)

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
        print(f"Gathering source code statistics for {repo_url}...")
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
                        hashObj['path'] = filesArr
                        finalArr.append(hashObj)
                        filesArr = []
                    prevHash = lineArr[0]

        debugLog(finalArr, "finalArr")

        git_output_file = os.path.join(output_dir, repo_name + ".git.log.json")
        with open(git_output_file, 'w') as f:
            f.write(json.dumps(finalArr))
        upload(git_output_file, config, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/git")

        print(f"Gathering file sizes for {repo_url}...")
        # Sizes for writing to output file
        # Intialize file list with "." as total size
        sizes = {
            "files":{
                ".":{
                    "size" : get_size(temp_dir),
                    "loc" : 0,
                    "ext" : None,
                    "directory" : True
                }
            }
        }
        #filelist for multimetric
        filelist = []

        for path, subdirs, list in os.walk(temp_dir):
            for name in list:
                fp = os.path.join(path, name)
                rp = fp.replace(temp_dir, '.') # Just save relative path
                if allowfile(fp):
                    file = {
                        "size" : os.path.getsize(fp),
                        "loc" : getloc(fp),
                        "ext" : os.path.splitext(name)[1],
                        "directory" : False
                    }
                    sizes["files"][rp] = file
                    filelist.append(fp)

        sizes_output_file = os.path.join(output_dir, repo_name + ".sizes.json")
        with open(sizes_output_file, 'w') as f:
            f.write(str(sizes))

        print(f"Analyzing repository {repo_url} with Multimetric...")
        stats_output_file = os.path.join(output_dir, repo_name + ".stats.json")
        stats_error_file = os.path.join(output_dir, repo_name + ".stats.err")

        # Calling multimetric with subproccess works, but we might want to call
        # Multimetric directly, ala lines 91-110 from multimetric main
        with open(stats_output_file, 'w') as f:
            with open(stats_error_file, 'w') as e:
                subprocess.check_call(["multimetric"] + filelist, stdout=f, stderr=e, encoding='utf-8')
        upload(stats_output_file, config, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/stats")

        print(f"Scanning repository {repo_url}...")
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
        upload(findings_output_file, config, f"/report/{config['report']['id']}/CorsisCode/{corsisId}/{repo_name}/findings")

        os.chdir("..")
        #shutil.rmtree(temp_dir)

    print("All done.")

# For test runs from commandline. Comment out before packaging.
main()

