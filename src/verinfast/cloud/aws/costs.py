import json
import os
import subprocess

from verinfast.utils.utils import DebugLog
from verinfast.cloud.aws.get_profile import find_profile
debugLog = DebugLog(os.getcwd())


def runAws(targeted_account, start, end, path_to_output,
           profile=None, log=debugLog.log, dry=False):

    def _get_costs_and_usage(profile: str, aws_output_file: str):
        cmd = f'''
            aws ce get-cost-and-usage \
            --time-period Start={start},End={end} \
            --granularity=DAILY \
            --metrics "BlendedCost" \
            --group-by Type=DIMENSION,Key=SERVICE \
            --profile="{profile}" \
            --output=json | cat
        '''

        try:
            results = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                check=True
            )

        except subprocess.CalledProcessError:
            log(msg="Error getting data from AWS CLI get-cost-and-usage",
                tag="AWS CLI")
            raise Exception("Error getting aws cli data.")

        text = results.stdout.decode()
        if text is None or isinstance(text, str) is False:
            log(msg="No data returned from AWS CLI get-cost-and-usage",
                tag="AWS CLI")
            return None

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

        with open(aws_output_file, 'w') as outfile:
            outfile.write(json.dumps(upload, indent=4))
        return aws_output_file

    if profile is None:
        profile = find_profile(targeted_account=targeted_account, log=log)

    if profile is None:
        log(msg="No matching profiles found",
            tag=targeted_account)
        return None

    output_file = os.path.join(
        path_to_output,
        f'aws-cost-{targeted_account}.json'
    )
    if not dry:
        _get_costs_and_usage(profile, output_file)

    return output_file
