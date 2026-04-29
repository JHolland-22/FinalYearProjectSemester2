import aws_cdk as cdk
from aws_cdk import Stack, aws_s3 as s3, aws_iam as iam, RemovalPolicy, CfnOutput
from constructs import Construct

class LabsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for storing lab PDF files organised by category (Security, Networking, Databases)
        # Include the AWS account ID in the bucket name to avoid naming conflicts
        self.labs_bucket = s3.Bucket(
            self, "LabsBucket",
            bucket_name=f"student-labs-{cdk.Aws.ACCOUNT_ID}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            # Public access is not blocked because the Flask app running in the AWS Academy account
            # uses unsigned S3 requests to read labs cross-account
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False
            )
        )

        # Allow anyone to read lab files from the bucket
        # This enables the Flask app in the Academy account to list and download lab PDFs
        self.labs_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="PublicReadForEducation",
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                self.labs_bucket.bucket_arn,
                f"{self.labs_bucket.bucket_arn}/*"
            ]
        ))

        # Allow anyone to upload, read, list, and delete lab files
        # This is needed because the Academy account credentials cannot access cross-account S3
        # without a permissive bucket policy, so educators can upload and manage labs from the web app
        self.labs_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="AllowAnyAccount",
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"],
            resources=[
                self.labs_bucket.bucket_arn,
                f"{self.labs_bucket.bucket_arn}/*"
            ]
        ))

        # Output the bucket name so it can be used as an environment variable for the Flask app
        CfnOutput(self, "BucketName", value=self.labs_bucket.bucket_name)