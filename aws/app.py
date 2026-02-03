#!/usr/bin/env python3
import aws_cdk as cdk
from auth_stack import AuthStack
import os

app = cdk.App()

AuthStack(app, "AuthStack",
    env=cdk.Environment(
        region="eu-west-1"
    )
)

app.synth()
