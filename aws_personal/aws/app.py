#!/usr/bin/env python3
import aws_cdk as cdk
from auth_stack import AuthStack
from labs_stack import LabsStack
from temp_stack import TemplatesStack
import os

# Entry point for the AWS CDK application
# Defines and deploys three CloudFormation stacks to the personal AWS account:
# 1. AuthStack : Cognito User Pool for student and educator authentication
# 2. LabsStack : S3 bucket for storing lab PDF files
# 3. TemplatesStack : S3 bucket for storing launch template JSON files

app = cdk.App()

# Authentication stack : creates the Cognito User Pool, app client, user groups,
# and the post-confirmation Lambda that auto-assigns users to roles
AuthStack(app, "AuthStack",
    env=cdk.Environment(
        region="us-east-1"
    )
)

# Labs stack : creates the S3 bucket for lab PDFs with cross-account access policies
# so the Flask app in the AWS Academy account can read and upload labs
LabsStack(app, "LabsStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region="us-east-1"
    )
)

# Templates stack : creates the S3 bucket for launch template JSON files
# with cross-account access policies so educators can manage templates from the web app
TemplatesStack(app, "TemplatesStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region="us-east-1"
    )
)

# Generate CloudFormation templates from the CDK app for deployment
app.synth()