import os
from google.cloud.monitoring_v3 import query, QueryServiceClient

os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/Users/jason/.config/gcloud/application_default_credentials.json"

def getBlocks(sub_id:str):
    client = QueryServiceClient()
    q = query.Query(
        client=client, 
        project=sub_id, 
        metric_type='storage.googleapis.com/storage/total_bytes',
        days=1
    )
    df = q.as_dataframe()
    print(df)

getBlocks(sub_id="startupos-328814")
