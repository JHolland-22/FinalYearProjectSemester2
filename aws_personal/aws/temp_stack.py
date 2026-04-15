import aws_cdk as cdk
from aws_cdk import Stack, aws_s3 as s3, aws_iam as iam, RemovalPolicy, CfnOutput
from constructs import Construct

class TemplatesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.templates_bucket = s3.Bucket(
            self, "TemplatesBucket",
            bucket_name=f"launch-templates-{cdk.Aws.ACCOUNT_ID}",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False
            )
        )

        self.templates_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="PublicReadForEducation",
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                self.templates_bucket.bucket_arn,
                f"{self.templates_bucket.bucket_arn}/*"
            ]
        ))

        self.templates_bucket.add_to_resource_policy(iam.PolicyStatement(
            sid="AllowAnyAccount",
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"],
            resources=[
                self.templates_bucket.bucket_arn,
                f"{self.templates_bucket.bucket_arn}/*"
            ]
        ))

        CfnOutput(self, "BucketName", value=self.templates_bucket.bucket_name)