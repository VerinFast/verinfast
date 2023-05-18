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

def main():
    config = setup()
    scan(config)

##### Helpers #####
def get_size(start_path = '.'):
    total_size = 0
    gitpattern = re.compile("^(.*\.git.*)$")
    for dirpath, dirnames, filenames in os.walk(start_path):
        if not gitpattern.match(dirpath):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    return total_size

###### SETUP ######
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

    # TODO this should be an import and be handled by the package install
    # Check if multimetric is installed, if not install it
    if not shutil.which("multimetric"):
        subprocess.check_call(["pip", "install", "git+https://github.com/aylusltd/multimetric.git"])
        print("Multimetric is installed.")
    else:
        print("Multimetric already installed.")
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

        output_file = os.path.join(output_dir, repo_name + ".stats.json")
        error_file = os.path.join(output_dir, repo_name + ".stats.err")

        # Intialize file list with "." as total size
        files = {
            "files":{
                ".":{
                    "size" : get_size(temp_dir),
                    "loc" : 0,
                    "ext" : None,
                    "directory" : True
                }
            }
        }
        print(files["files"])
        for path, subdirs, filelist in os.walk(temp_dir):
            for name in filelist:
                fp = os.path.join(path, name)
                file = {
                    "size" : os.path.getsize(fp),
                    "loc" : 0,
                    "ext" : os.path.splitext(name)[1],
                    "directory" : False
                }
                files["files"][fp] = file
        print(files)
        exit()
        # TODO Crawl repo for file list and pass in list of files
        with open(output_file, 'w') as f:
            with open(error_file, 'w') as e:
                subprocess.check_call(["multimetric", "."], stdout=f, stderr=e)

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

