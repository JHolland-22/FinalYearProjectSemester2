#!/usr/bin/env python3
import aws_cdk as cdk
from auth_stack import AuthStack
from labs_stack import LabsStack
from temp_stack import TemplatesStack
import os

app = cdk.App()

AuthStack(app, "AuthStack",
    env=cdk.Environment(
        region="us-east-1"
    )
)

LabsStack(app, "LabsStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region="us-east-1"
    )
)

TemplatesStack(app, "TemplatesStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region="us-east-1"
    )
)

app.synth()
