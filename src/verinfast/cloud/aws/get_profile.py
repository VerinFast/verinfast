import json
import os
import subprocess

from verinfast.utils.utils import DebugLog


debugLog = DebugLog(os.getcwd())


def find_profile(targeted_account: str, log=debugLog.log):
    profiles = []
    available_accounts = []
    results = subprocess.run(
        "aws configure list-profiles",
        shell=True,
        stdout=subprocess.PIPE
    )
    text = results.stdout.decode()

    for line in text.splitlines():
        profiles.append(line)
        cmd = f"aws sts get-caller-identity --profile={line} --output=json"
        try:
            results = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                check=True
            )
        except subprocess.CalledProcessError:
            # TODO make some log message that makes sense
            continue
        text = results.stdout.decode()
        identity = json.loads(text)
        account = identity["Account"]
        available_accounts.append(account)

        if str(account) == str(targeted_account):
            return line

    debugLog.log(msg=profiles, tag="AWS Profiles")
    debugLog.log(msg=available_accounts, tag="AWS Available Accounts")
