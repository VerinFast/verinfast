import json
import os
import subprocess
from verinfast.cloud.aws.get_profile import find_profile


def get_aws_costs(
    targeted_account, start, end, path_to_output, log, profile=None, dry=False
):

    def _get_costs_and_usage(profile: str, aws_output_file: str, next_token=None):
        base_cmd = f"""
            aws ce get-cost-and-usage \
            --time-period Start={start},End={end} \
            --granularity=DAILY \
            --metrics "BlendedCost" \
            --group-by Type=DIMENSION,Key=SERVICE \
            --profile="{profile}" \
            --output=json"""

        cmd = f'{base_cmd} --next-token="{next_token}" | cat'
        if next_token:
            cmd = f'{base_cmd} --next-token="{next_token}" | cat'
        else:
            cmd = f"{base_cmd} | cat"

        try:
            results = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, check=True
            )

        except subprocess.CalledProcessError:
            log(msg="Error getting data from AWS CLI get-cost-and-usage", tag="AWS CLI")
            raise Exception("Error getting aws cli data.")

        text = results.stdout.decode()

        if not text or not isinstance(text, str):
            log(msg="No data returned from AWS CLI get-cost-and-usage", tag="AWS CLI")
            return None

        return json.loads(text)

    def _process_results(obj):
        charges = []
        results_by_time = obj.get("ResultsByTime", [])
        for charge in results_by_time:
            if charge.get("Groups"):
                for group in charge["Groups"]:
                    newCharge = {
                        "Date": charge["TimePeriod"]["Start"],
                        "Group": group["Keys"][0],
                        "Cost": group["Metrics"]["BlendedCost"]["Amount"],
                        "Currency": group["Metrics"]["BlendedCost"]["Unit"],
                    }
                    charges.append(newCharge)
        return charges

    def _get_all_costs(profile: str, aws_output_file: str):
        all_charges = []
        next_token = None

        while True:
            # Get results for current page
            obj = _get_costs_and_usage(profile, aws_output_file, next_token)
            if not obj:
                break

            # Process and append results
            charges = _process_results(obj)
            all_charges.extend(charges)

            # Check for next page
            next_token = obj.get("NextPageToken")
            if not next_token:
                break

            log(
                msg=f"Fetching next page of results with token: "
                f"{next_token[:10]}...",
                tag="AWS CLI",
            )

        # Create final upload object
        upload = {
            "metadata": {"provider": "aws", "account": str(targeted_account)},
            "data": all_charges,
        }

        # Write results to file
        with open(aws_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))

        return aws_output_file

    if profile is None:
        profile = find_profile(targeted_account=targeted_account, log=log)

    if profile is None:
        log(msg="No matching profiles found", tag=targeted_account)
        return None

    output_file = os.path.join(path_to_output, f"aws-cost-{targeted_account}.json")

    if not dry:
        _get_all_costs(profile, output_file)

    return output_file
