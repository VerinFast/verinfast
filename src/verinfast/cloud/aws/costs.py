import json
import os
import subprocess

from verinfast.utils.utils import DebugLog
debugLog = DebugLog(os.getcwd())


def runAws(targeted_account, start, end, path_to_output):
    results = subprocess.run(
        'aws configure list-profiles',
        shell=True,
        stdout=subprocess.PIPE
    )

    text = results.stdout.decode()
    profiles = []
    available_accounts = []
    for line in text.splitlines():
        profiles.append(line)
        cmd = f'aws sts get-caller-identity --profile={line}'
        results = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        text = results.stdout.decode()
        identity = json.loads(text)
        account = identity["Account"]
        available_accounts.append(account)
        if str(account) == str(targeted_account):
            cmd = f'''
                aws ce get-cost-and-usage \
                --time-period Start={start},End={end} \
                --granularity=DAILY \
                --metrics "BlendedCost" \
                --group-by Type=DIMENSION,Key=SERVICE \
                --profile={line} | cat
            '''

            try:
                results = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE
                )

            except subprocess.CalledProcessError:
                raise Exception("Error getting aws cli data.")

            text = results.stdout.decode()
            obj = json.loads(text)
            results_by_time = obj["ResultsByTime"]
            charges = []
            for charge in results_by_time:
                if charge["Groups"]:
                    for group in charge["Groups"]:
                        newCharge = {
                            "Date": charge["TimePeriod"]["Start"],
                            "Group": group["Keys"][0],
                            "Cost": group["Metrics"]["BlendedCost"]["Amount"],
                            "Currency": group["Metrics"]["BlendedCost"]["Unit"]
                        }
                        charges.append(newCharge)
            upload = {
                "metadata": {
                    "provider": "aws",
                    "account": str(targeted_account)
                },
                "data": charges
            }
            aws_output_file = os.path.join(
                path_to_output,
                f'aws-cost-{targeted_account}.json'
            )

            with open(aws_output_file, 'w') as outfile:
                outfile.write(json.dumps(upload, indent=4))
            return aws_output_file
    debugLog.log(msg=profiles, tag="AWS Profiles")
    debugLog.log(msg=available_accounts, tag="AWS Available Accounts")
