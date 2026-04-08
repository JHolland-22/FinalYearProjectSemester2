import aws_cdk as cdk
from aws_cdk import Stack, aws_s3 as s3, aws_iam as iam, RemovalPolicy, CfnOutput
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
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,
                ignore_public_acls=True,
                block_public_policy=False,
                restrict_public_buckets=False
            )
        )

        # Public read policy - create PolicyStatement directly
        bucket_policy = iam.PolicyStatement(
            sid="PublicReadForEducation",
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                self.labs_bucket.bucket_arn,
                f"{self.labs_bucket.bucket_arn}/*"
            ]
        )

        # Add the statement directly
        self.labs_bucket.add_to_resource_policy(bucket_policy)

        CfnOutput(self, "BucketName", value=self.labs_bucket.bucket_name)