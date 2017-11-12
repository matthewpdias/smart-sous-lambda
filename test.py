import boto3

for bucket in s3.buckets.all():
    print(bucket.name)