#!/usr/bin/env python3
import aws_cdk as cdk
from auth_stack import AuthStack

app = cdk.App()
AuthStack(app, "AuthStack")
app.synth()
