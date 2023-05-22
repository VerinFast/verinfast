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
#  - Install this package with "python setup.py install"
#  - In a directory with a "config.yaml" file run
#    "sosagent"
#
#  Troubleshooting:
#  - Run "python3 -m pip install --upgrade pip setuptools wheel"
#
#  Copyright 2023 Startos Inc.
#
##################################################################################

import subprocess
import importlib
import sys
import os
import yaml
import requests
import shutil
import re
from multimetric.fp import file_process
#import multimetric #This does nothing
#print(dir(multimetric))

def main():
    config = setup()
    scan(config)

##### Helpers #####
newline = "\n" # TODO - Set to system appropriate newline character. This doesn't work with multimetric

# Excludes files in .git directories. Takes path of full path with filename
def allowfile(path):
    gitpattern = re.compile("^(.*\.git.*)$")
    if not gitpattern.match(path):
        return True
    else:
        return False

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        if allowfile(dirpath):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
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

        try:
            subprocess.check_call(["git", "checkout", "master"])
        except subprocess.CalledProcessError:
            subprocess.check_call(["git", "checkout", "main"])

        print(f"Analyzing repository {repo_url} with Multimetric...")

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
            if allowfile(path):
                for name in list:
                    fp = os.path.join(path, name)
                    file = {
                        "size" : os.path.getsize(fp),
                        "loc" : getloc(fp),
                        "ext" : os.path.splitext(name)[1],
                        "directory" : False
                    }
                    sizes["files"][fp] = file
                    filelist.append(fp)

        sizes_output_file = os.path.join(output_dir, repo_name + ".sizes.json")
        with open(sizes_output_file, 'w') as f:
            f.write(str(sizes))
            #f.write(filelist)

        stats_output_file = os.path.join(output_dir, repo_name + ".stats.json")
        stats_error_file = os.path.join(output_dir, repo_name + ".stats.err")

        # print(filelist)
        # exit(255)

        # Calling multimetric with subproccess works, but we might want to call
        # Multimetric directly, ala lines 91-110 from multimetric main

        with open(stats_output_file, 'w') as f:
            with open(stats_error_file, 'w') as e:
                subprocess.check_call(["multimetric"] + filelist, stdout=f, stderr=e, encoding='utf-8')

        # with open(output_file, 'rb') as f:
        #     response = requests.post(config['baseurl'] + TODO_API_ROUTE, files={'file': f})

        # if response.status_code == 200:
        #     print(f"Successfully uploaded multimetric output for {repo_url} to the REST API.")
        # else:
        #     print(f"Failed to upload multimetric output for {repo_url} to the REST API.")

        os.chdir("..")
        #shutil.rmtree(temp_dir)

    print("All done.")

# For test runs from commandline. Comment out before packaging.
main()

