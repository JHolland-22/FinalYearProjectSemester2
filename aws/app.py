#!/usr/bin/env python3
import aws_cdk as cdk
from auth_stack import AuthStack
from labs_stack import LabsStack
import os

app = cdk.App()

AuthStack(app, "AuthStack",
    env=cdk.Environment(
        region="eu-west-1"
    )
)

LabsStack(app, "LabsStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

app.synth()
