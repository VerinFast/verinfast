import http.client
import json
import os
import re
import ssl
import subprocess


def runAzure(subscription_id, start, end, path_to_output, log, dry=False):
    if not dry:
        ssl.SSLContext.verify_mode = property(
            lambda self: ssl.CERT_OPTIONAL, lambda self, newval: None
        )

        conn = http.client.HTTPSConnection("management.azure.com")
        subprocess.run(f"az account set --subscription {subscription_id}", shell=True)
        # results = subprocess.run(f'az account show --query id" -o tsv', shell=True, stdout=subprocess.PIPE)
        # subscription_id = results.stdout.decode()[:-1]
        # 80dc7a6b-df94-44be-a235-7e7ade335a3c
        req_path = (
            f"/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query"
        )
        req_params = "api-version=2023-03-01"
        body = {
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [{"type": "Dimension", "name": "ServiceName"}],
            },
            "timeframe": "custom",
            "timePeriod": {"from": str(start), "to": str(end)},
            "type": "ActualCost",
        }
        results = subprocess.run(
            "az account get-access-token --resource=https://management.azure.com/ --query accessToken -o tsv",
            shell=True,
            stdout=subprocess.PIPE,
        )

        bearer_token = "Bearer " + results.stdout.decode().strip()
        # print(bearer_token)
        print("Fetching data for subscription: " + subscription_id)
        conn.request(
            "POST",
            req_path + "?" + req_params,
            headers={"Authorization": bearer_token, "Content-Type": "application/json"},
            body=json.dumps(body),
        )
        response = conn.getresponse()
        print("Parsing response")
        data = json.loads(response.read().decode())
        if "error" in data:
            log(msg=json.dumps(data["error"]), tag="Azure error")
            return

        with open(f"{path_to_output}/azure_output_raw.json", "w") as outfile:
            outfile.write(json.dumps(data, indent=4))

        vals = data["properties"]["rows"]
        new_vals = []
        for val in vals:
            nv = {
                "Date": str(val[1]),
                "Cost": str(val[0]),
                "Group": val[2],
                "Currency": val[3],
            }
            s = nv["Date"]
            if re.match("^[0-9]*$", s) and len(s) == 8:
                nv["Date"] = s[0:4] + "-" + s[4:6] + "-" + s[6:8]
            new_vals.append(nv)
        upload = {
            "metadata": {"provider": "azure", "account": subscription_id},
            "data": new_vals,
        }
    # End dry block

    az_output_file = os.path.join(path_to_output, f"az-cost-{subscription_id}.json")

    if not dry:
        with open(az_output_file, "w") as outfile:
            outfile.write(json.dumps(upload, indent=4))

    return az_output_file
