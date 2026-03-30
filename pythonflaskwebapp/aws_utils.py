import boto3
from flask import session


def ec2_client_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, region="us-east-1"):
    return boto3.client(
        "ec2",
        region_name=region,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token
    )

def list_user_amis_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, region="us-east-1"):
    ec2 = ec2_client_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, region)
    own_images = ec2.describe_images(Owners=["self"])["Images"]
    shared_images = ec2.describe_images(ExecutableUsers=["self"])["Images"]
    all_images = {img["ImageId"]: img for img in own_images + shared_images}
    return list(all_images.values())



def share_user_ami_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, ami_id, target_account_ids, region="us-east-1"):
    ec2 = ec2_client_from_session(aws_access_key_id, aws_secret_access_key, aws_session_token, region)

    ec2.modify_image_attribute(
        ImageId=ami_id,
        LaunchPermission={"Add": [{"UserId": acc} for acc in target_account_ids]}
    )

    image = ec2.describe_images(ImageIds=[ami_id])["Images"][0]
    for mapping in image.get("BlockDeviceMappings", []):
        if "Ebs" in mapping:
            snap_id = mapping["Ebs"]["SnapshotId"]
            ec2.modify_snapshot_attribute(
                SnapshotId=snap_id,
                Attribute="createVolumePermission",
                OperationType="add",
                UserIds=target_account_ids
            )


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


def get_s3_read_client():
    from botocore import UNSIGNED
    from botocore.config import Config
    return boto3.client('s3', config=Config(signature_version=UNSIGNED), region_name='us-east-1')