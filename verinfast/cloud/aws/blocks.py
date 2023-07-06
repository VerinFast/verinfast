from datetime import datetime, timedelta
import boto3

def getBlocks():
    bucket_name = 'BUCKET-NAME'
    cloudwatch = boto3.client('cloudwatch')
    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/S3",
        MetricName="BucketSizeBytes",
        Dimensions=[
            {
                "Name": "BucketName",
                "Value": bucket_name
            },
            {
                "Name": "StorageType",
                "Value": "StandardStorage"
            }
        ],
        StartTime=datetime.now() - timedelta(days=1),
        EndTime=datetime.now(),
        Period=86400,
        Statistics=['Average']
    )

    bucket_size_bytes = response['Datapoints'][-1]['Average']
    print(bucket_size_bytes)

getBlocks()