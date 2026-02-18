import aws_cdk as cdk
from aws_cdk import Stack, aws_s3 as s3, RemovalPolicy, CfnOutput
from constructs import Construct


class LabsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for storing lab PDFs
        self.labs_bucket = s3.Bucket(
            self, "LabsBucket",
            bucket_name=f"student-labs-{cdk.Aws.ACCOUNT_ID}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        )

        # Output bucket name so Flask app can use it
        CfnOutput(
            self, "BucketName",
            value=self.labs_bucket.bucket_name
        )
