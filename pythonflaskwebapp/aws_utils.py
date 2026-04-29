import boto3
from flask import session


# Creates an EC2 client using AWS credentials stored in the session
# Used for actions like launching starting stopping and describing instances
def ec2_client_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, region="us-east-1"):
    return boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token
    )




# Creates an S3 client using credentials from the session
# Falls back to default AWS configuration if no credentials are stored
def get_s3_client():
    if session.get('aws_access_key_id'):
        return boto3.client(
            's3',
            aws_access_key_id=session.get('aws_access_key_id'),
            aws_secret_access_key=session.get('aws_secret_access_key'),
            aws_session_token=session.get('aws_session_token')
        )
    else:
        return boto3.client('s3')





# Creates a read only S3 client that does not require signed credentials
# Used for accessing objects where authentication is not required
def get_s3_read_client():
    from botocore import UNSIGNED
    from botocore.config import Config

    return boto3.client(
        's3',
        config=Config(signature_version=UNSIGNED),
        region_name='us-east-1'
    )