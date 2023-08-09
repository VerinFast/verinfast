# VerinFast™

 Welcome to the Scanning Agent.

 This tool safely and securely analyzes applications for benchmarking.

## Requirements:
 - Python3 - Test with `python3 --version`
 - pip - Test with `pip -V`
 - SSH access to code repositories - Test with `git status`
 - Command line tool access to cloud hosting providers
 - Admin privileges on the computer used to run the agent
 - Outbound internet access (for posting results and fetching dependency metadata)
 - Your dependency mangement tools (e.g. `npm` or `yarn` or `maven`)

## To run the Agent:
 - Install this package with `python3 setup.py install --user`
 - In a directory with a `config.yaml` file run
   `verinfast`

 
## Troubleshooting:
### Python
 - Run `python3 -m pip install --upgrade pip setuptools wheel`
### git
 - Run `which git`, `git --version`
 - Run ` ssh -vT git@github.com` to test access to GitHub
###  AWS
 - Run `which aws`, `aws --version`
### Azure
 - Run `az git`, `az --version`
 - Run `az account subscription list` to check subscription Id
### Semgrep
 - Run `which semgrep`, `semgrep --version`
### pip
 - Run `which pip`
 - If no `pip``, run:
    `curl -o get-pip.py https://bootstrap.pypa.io/get-pip.py`
    `python get-pip.py`  OR `python3 get-pip.py`
 Run `sudo apt update`

 Copyright 2023 Startos Inc.
